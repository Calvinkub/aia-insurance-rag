# Narration and soundtrack plan (Thai)

Written for the person recording the demo video. Timings match the Remotion composition `AiaDemo` (54 s, 30 fps).
The timings are the scene boundaries, not a measured fit: several lines are probably too long to say calmly in the
time shown (calm Thai is roughly 4-5 syllables per second). Record the narration first, then retime the scenes in
`src/Motion.tsx` (`SCENES[].frames`) to the real audio length instead of rushing the voice.
Say the English technical terms as they are written.

## Part A: motion graphic, opening (0:00 - 0:30)

| Time | Scene | Narration |
|---|---|---|
| 0:00 - 0:04 | Title | สวัสดีครับ นี่คือโปรเจกต์ AIA Brochure Q&A ถามเรื่องประกัน แล้วได้คำตอบพร้อมหน้าอ้างอิง |
| 0:04 - 0:11 | Problem | ถ้าถามโมเดลตรงๆ โดยไม่มีเอกสาร มันตอบถูกแค่ 2 จาก 28 ข้อ และยังตอบข้อที่ไม่มีในเอกสารอีก 3 จาก 6 ข้อ แต่เมื่อใช้ RAG ตอบถูก 26 จาก 28 และไม่ตอบข้อที่ไม่มีในเอกสารเลย |
| 0:11 - 0:20 | Pipeline | คำถามผ่าน hybrid retriever ที่รวม BM25 กับ embedding จากนั้น gemma ตอบเป็น JSON ที่ถูกตรวจ schema ทุก citation ต้องมี quote ที่อยู่ในข้อความจริง และ agent เรียก tool ได้สูงสุด 6 step แล้วหยุด |

## Part B: live demo, screen recording (about 2:00 - 3:30, no motion graphic)

Warm the cache first: ask one question before recording, because the proxy embeds slowly.

| Step | What you do on screen | Narration |
|---|---|---|
| B1 | Open `/`, RAG mode. Ask "What is the waiting period of AIA CI Care?" | มาดูตัวอย่างที่ตอบได้ สังเกตว่า sources ขึ้นก่อน แล้วคำตอบตามมา พร้อม citation ที่ขึ้นสถานะ verified |
| B2 | Ask about Vitality reward tiers | คำถามนี้ไม่มีในโบรชัวร์ ระบบปฏิเสธแทนที่จะเดา |
| B3 | Switch to Agent mode. Ask a two-product comparison | โหมด agent เรียก search หลายรอบ แล้วใช้ calculate เมื่อต้องคำนวณ ดู tool call ที่ขึ้นทีละขั้น |
| B4 | Ask the A07 question | ตอนนี้ถึงกรณีล้มเหลว ระบบตอบ 44 แต่ gold label คือ 40 |

## Part C: motion graphic, closing (0:20 - 0:54 of the graphic)

| Time | Scene | Narration |
|---|---|---|
| 0:20 - 0:30 | Results | วัดบน gold set 34 ข้อ hybrid RAG ได้ accuracy 0.93 เท่ากับ BM25 ส่วน hybrid ดีขึ้นที่ MRR และ citation ที่ตรวจผ่าน แต่ต่างกันแค่ 1-2 ข้อ จึงเป็นเพียงทิศทาง ผมลองตั้ง min_score ผลคือแย่ลง 1 ข้อ จึงตั้งเป็น 0 |
| 0:30 - 0:37 | Chunking | ผมลอง chunking อีก 4 แบบ ได้แก่ ลบ boilerplate, ตาราง markdown, context จาก LLM และ parent-child ไม่มีแบบไหนชนะ baseline ชัดเจน ความต่างอยู่ในระดับ noise |
| 0:37 - 0:47 | Failure | กลับมาที่ A07 ครั้งแรกผมคิดว่าโมเดล hallucinate แต่เมื่อเปิดดูโบรชัวร์ หน้า 1 เขียน 44 ส่วนหัวตารางหน้า 2 เขียน 40 โบรชัวร์ขัดแย้งกันเอง โมเดลตอบตามหน้า 1 ซึ่งมีหลักฐาน สิ่งที่ระบบยังขาดคือการแจ้งความขัดแย้งนี้ |
| 0:47 - 0:54 | Outro | ข้อจำกัดคือ eval เล็กและปรับจูนบนชุดเดียวกัน ไม่มี held-out set และยังไม่ได้ประเมิน agent เชิงปริมาณ โค้ดและรายงานอยู่ใน GitHub ขอบคุณครับ |

If a line runs long, cut the second sentence or lengthen the scene; do not rush the voice.

## Soundtrack brief (for Google AI Studio or any music model)

Use this as the prompt. Generate about 60 s so the track covers the 54 s graphic plus a fade.

> Calm, minimal electronic background music for a technical project presentation. Soft ambient pads, gentle pulsing
> synth, light percussion, around 90 BPM, steady and unobtrusive, no vocals, no lyrics, no sudden changes.
> Sits well under a voice-over. Slight lift in the middle, resolves softly at the end.

Constraints for the track:
- Instrumental only, so it does not compete with the narration.
- Keep it quiet: mix at roughly -20 dB under the voice.
- Check the licence terms of the generated track before submitting the video publicly.

## Adding the music to the video

1. Save the track as `demo-video/public/soundtrack.mp3`.
2. In `src/Motion.tsx`, add inside the component:

   ```tsx
   import { Audio } from "@remotion/media";
   import { staticFile, interpolate } from "remotion";
   // ...
   <Audio
     src={staticFile("soundtrack.mp3")}
     volume={(f) => interpolate(f, [0, 30, TOTAL - 45, TOTAL], [0, 0.18, 0.18, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
   />
   ```

3. Run `npx remotion add @remotion/media` first if the package is missing.
