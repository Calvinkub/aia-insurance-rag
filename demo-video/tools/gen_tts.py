"""Generate the Thai voice-over with Gemini TTS, one WAV per scene, and check each clip by transcribing it back.

Reads GEMINI_API_KEY from demo-video/.env (git-ignored) and never prints it.
Usage: python tools/gen_tts.py [segment ...]     (no args = all segments)
Writes public/audio/<segment>.wav and src/audio.json (segment -> duration in seconds).
"""
import audioop
import base64
import json
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TTS_MODEL = "gemini-3.8-flash-tts"
CHECK_MODEL = "gemini-3.6-flash"
VOICE = "Kore"
BASE = "https://generativelanguage.googleapis.com/v1beta/models"

SEGMENTS = {
    "title": "สวัสดีครับ นี่คือโปรเจกต์ AIA Brochure Q and A ถามเรื่องประกัน แล้วได้คำตอบพร้อมหน้าอ้างอิง",
    "problem": "ถ้าถามโมเดลตรงๆ โดยไม่มีเอกสาร มันตอบถูกแค่ 2 จาก 28 ข้อ และยังตอบข้อที่ไม่มีในเอกสารอีก 3 จาก 6 ข้อ "
               "แต่เมื่อใช้ RAG ตอบถูก 26 จาก 28 และไม่ตอบข้อที่ไม่มีในเอกสารเลย",
    "pipeline": "คำถามผ่าน hybrid retriever ที่รวม BM25 กับ embedding จากนั้น gemma ตอบเป็น JSON ที่ถูกตรวจ schema "
                "ทุก citation ต้องมี quote ที่อยู่ในข้อความจริง และ agent เรียก tool ได้สูงสุด 6 step แล้วหยุด",
    "results": "วัดบน โกลด์เซ็ต 34 ข้อ hybrid RAG ได้ accuracy 0.93 เท่ากับ BM25 ส่วน hybrid ดีขึ้นที่ MRR และ citation ที่ตรวจผ่าน "
               "แต่ต่างกันแค่หนึ่งถึงสองข้อ จึงเป็นเพียงทิศทาง ผมลองตั้ง min score ผลคือแย่ลงหนึ่งข้อ จึงตั้งเป็นศูนย์",
    "chunking": "ผมลอง chunking อีกสี่แบบ ได้แก่ ลบ boilerplate ตาราง markdown context จาก LLM และ parent child "
                "ไม่มีแบบไหนชนะ baseline ชัดเจน ความต่างอยู่ในระดับ noise",
    "failure": "กลับมาที่ A07 ครั้งแรกผมคิดว่าโมเดล hallucinate แต่เมื่อเปิดดูโบรชัวร์ หน้าหนึ่งเขียน 44 ส่วนหัวตารางหน้าสองเขียน 40 "
               "โบรชัวร์ขัดแย้งกันเอง โมเดลตอบตามหน้าหนึ่งซึ่งมีหลักฐาน สิ่งที่ระบบยังขาดคือการแจ้งความขัดแย้งนี้",
    "outro": "ข้อจำกัดคือ eval เล็กและปรับจูนบนชุดเดียวกัน ไม่มี held out set และยังไม่ได้ประเมิน agent เชิงปริมาณ "
             "โค้ดและรายงานอยู่ใน GitHub ขอบคุณครับ",
    "demo1": "มาดูตัวอย่างที่ตอบได้ สังเกตว่า sources ขึ้นก่อน แล้วคำตอบตามมา พร้อม citation ที่ขึ้นสถานะ verified",
    "demo2": "คำถามนี้ไม่มีในโบรชัวร์ ระบบปฏิเสธแทนที่จะเดา",
    "demo3": "โหมด agent เรียก search หลายรอบ แล้วใช้ calculate เมื่อต้องคำนวณ ดู tool call ที่ขึ้นทีละขั้น",
    "demo4": "ตอนนี้ถึงกรณีล้มเหลว ระบบตอบ 44 แต่ gold label คือ 40",
}


def api_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("GEMINI_API_KEY missing in demo-video/.env")


def post(model: str, body: dict, key: str, retries: int = 4) -> dict:
    for attempt in range(retries):
        req = urllib.request.Request(f"{BASE}/{model}:generateContent", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            return json.load(urllib.request.urlopen(req, timeout=90))
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode(errors="replace")
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(20 * (attempt + 1))
                continue
            raise SystemExit(f"HTTP {e.code} from {model}: {msg}")
    raise SystemExit("unreachable")


def synth(text: str, key: str) -> bytes:
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    part = post(TTS_MODEL, body, key)["candidates"][0]["content"]["parts"][0]["inlineData"]
    return base64.b64decode(part["data"])  # raw 16-bit PCM, 24 kHz, mono


def trim_tail_burst(pcm: bytes, rate: int = 24000) -> bytes:
    """Gemini TTS ends every clip with a ~0.15 s loud burst (heard as static) after the speech has finished.

    The burst is always preceded by a stretch of near-silence. Cut back to the start of the last 50 ms window that is
    quiet if one exists in the final 0.6 s, so the clip ends in silence; otherwise leave the audio alone.
    """
    step = rate // 20 * 2  # 50 ms of 16-bit samples
    wins = [audioop.rms(pcm[i:i + step], 2) for i in range(0, len(pcm) - step + 1, step)]
    for back in range(1, min(12, len(wins)) + 1):
        if wins[-back] < 150:
            end = (len(wins) - back + 1) * step  # keep the quiet window, drop everything after it
            return pcm[:end]
    return pcm


def write_wav(path: Path, pcm: bytes) -> float:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    return len(pcm) / 2 / 24000


def transcribe(path: Path, key: str) -> str:
    body = {"contents": [{"parts": [
        {"text": "Transcribe this Thai audio exactly, including anything said before or after the main text. Output only the transcript."},
        {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(path.read_bytes()).decode()}}]}]}
    return post(CHECK_MODEL, body, key)["candidates"][0]["content"]["parts"][0]["text"].strip()


def main() -> None:
    key = api_key()
    names = sys.argv[1:] or list(SEGMENTS)
    out = ROOT / "public" / "audio"
    out.mkdir(parents=True, exist_ok=True)
    meta_path = ROOT / "src" / "audio.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for n in names:
        path = out / f"{n}.wav"
        meta[n] = round(write_wav(path, trim_tail_burst(synth(SEGMENTS[n], key))), 2)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        print(f"[{n}] {meta[n]} s\n  want: {SEGMENTS[n]}\n  heard: {transcribe(path, key)}", flush=True)


if __name__ == "__main__":
    main()
