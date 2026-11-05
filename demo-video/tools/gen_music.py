"""Generate the soundtrack with Lyria 3.5 through the Gemini Interactions API.

Reads GEMINI_API_KEY from demo-video/.env (git-ignored) and never prints it.
Usage: python tools/gen_music.py [output.mp3]
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT = (
    "Create a 1-minute instrumental track. Calm, minimal electronic background music for a technical project "
    "presentation. Soft ambient pads, a gentle pulsing synth, light percussion, around 90 BPM, steady and "
    "unobtrusive. No vocals, no lyrics, no sudden changes, so it sits well under a voice-over. A slight lift in "
    "the middle, resolving softly at the end."
)


def api_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("GEMINI_API_KEY missing in demo-video/.env")


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "public" / "soundtrack.mp3"
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps({"model": "lyria-3.5", "input": PROMPT}).encode(),
        headers={"Content-Type": "application/json", "Api-Revision": "2026-05-20", "x-goog-api-key": api_key()},
    )
    try:
        data = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read()[:600].decode(errors='replace')}")
    audio = [c["data"] for s in data.get("steps", []) if s.get("type") == "model_output"
             for c in s.get("content", []) if c.get("type") == "audio"]
    if not audio:
        raise SystemExit("no audio block in response: " + json.dumps(data)[:400])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(audio[-1]))
    texts = [c.get("text", "") for s in data.get("steps", []) if s.get("type") == "model_output"
             for c in s.get("content", []) if c.get("type") == "text"]
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    if texts:
        print("structure notes:\n" + "\n".join(texts)[:800])


if __name__ == "__main__":
    main()
