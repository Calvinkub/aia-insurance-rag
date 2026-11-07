import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { Bar, Card, Headline, Reveal, Scene, Sub } from "./ui";
import { C } from "./theme";

export const Title: React.FC = () => (
  <Scene>
    <div style={{ marginTop: 230 }}>
      <Reveal>
        <div style={{ fontSize: 44, color: C.teal, letterSpacing: 4 }}>LLM CAPSTONE</div>
      </Reveal>
      <Headline delay={8}>AIA Brochure Q&amp;A</Headline>
      <Sub delay={20}>ถามเรื่องประกัน AIA ประเทศไทย ได้คำตอบพร้อมหน้าอ้างอิง</Sub>
      <Sub delay={34}>หรือ "โบรชัวร์ไม่ได้ระบุ" แทนการเดา</Sub>
    </div>
  </Scene>
);

export const Problem: React.FC = () => (
  <Scene>
    <Headline>ถามโมเดลตรงๆ ได้อะไร?</Headline>
    <div style={{ display: "flex", gap: 56, marginTop: 70 }}>
      <Reveal delay={20} style={{ flex: 1 }}>
        <Card>
          <div style={{ fontSize: 44, color: C.red, fontWeight: 700 }}>closed-book (บังคับเดา)</div>
          <div style={{ fontSize: 150, fontWeight: 700, color: C.red }}>7%</div>
          <div style={{ fontSize: 40, color: C.dim }}>ตอบถูก 2 จาก 28 ข้อ</div>
          <div style={{ fontSize: 40, color: C.dim }}>ตอบ 3 จาก 6 ข้อที่ไม่มีในเอกสาร</div>
        </Card>
      </Reveal>
      <Reveal delay={50} style={{ flex: 1 }}>
        <Card>
          <div style={{ fontSize: 44, color: C.teal, fontWeight: 700 }}>hybrid RAG</div>
          <div style={{ fontSize: 150, fontWeight: 700, color: C.teal }}>93%</div>
          <div style={{ fontSize: 40, color: C.dim }}>ตอบถูก 26 จาก 28 ข้อ</div>
          <div style={{ fontSize: 40, color: C.dim }}>ไม่ตอบข้อที่ไม่มีในเอกสารเลย</div>
        </Card>
      </Reveal>
    </div>
  </Scene>
);

const STEPS = [
  { t: "คำถาม", s: "UI / REST / SSE", c: C.blue },
  { t: "Hybrid retriever", s: "BM25 + bge-m3 → RRF", c: C.amber },
  { t: "gemma-4-E4B-it", s: "temperature 0, JSON", c: C.blue },
  { t: "ตรวจ schema", s: "pydantic ModelAnswer", c: C.teal },
  { t: "คำตอบ + citation", s: "quote ต้องอยู่ใน passage", c: C.teal },
];

export const Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Scene>
      <Headline>ระบบทำงานอย่างไร</Headline>
      <div style={{ display: "flex", gap: 22, marginTop: 90, alignItems: "stretch" }}>
        {STEPS.map((st, i) => {
          const d = 20 + i * 24;
          const arrow = interpolate(frame, [d + 10, d + 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <React.Fragment key={st.t}>
              <Reveal delay={d} style={{ flex: 1 }}>
                <Card style={{ height: 300, borderColor: st.c, padding: "28px 24px" }}>
                  <div style={{ fontSize: 40, fontWeight: 700, color: st.c }}>{st.t}</div>
                  <div style={{ fontSize: 32, color: C.dim, marginTop: 16 }}>{st.s}</div>
                </Card>
              </Reveal>
              {i < STEPS.length - 1 ? (
                <div style={{ alignSelf: "center", fontSize: 56, color: C.dim, opacity: arrow }}>›</div>
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
      <div style={{ marginTop: 70 }}>
        <Sub delay={150} color={C.text}>
          Agent: search_brochures · list_products · calculate — สูงสุด 6 step แล้วหยุด
        </Sub>
        <Sub delay={170}>id ที่โมเดลแต่งขึ้นถูกทิ้ง และ citation ถูกตรวจกับข้อความจริง</Sub>
      </div>
    </Scene>
  );
};

export const Results: React.FC = () => (
  <Scene>
    <Headline>วัดผลบน gold set 34 ข้อ</Headline>
    <Sub delay={10}>accuracy ของคำตอบ (28 ข้อที่ตอบได้)</Sub>
    <div style={{ marginTop: 60 }}>
      <Bar label="closed-book (เดา)" value={0.07} shown="0.07" color={C.red} delay={30} />
      <Bar label="BM25 RAG" value={0.93} shown="0.93" color={C.blue} delay={60} />
      <Bar label="hybrid RAG (ใช้จริง)" value={0.93} shown="0.93" color={C.teal} delay={90} />
      <Bar label="hybrid + min_score 0.65" value={0.89} shown="0.89" color={C.amber} delay={120} />
    </div>
    <Sub delay={165} color={C.amber}>ผลลบ: min_score ตัด chunk ที่ถูกทิ้ง เสียไป 1 ข้อ → ตั้งค่าเป็น 0</Sub>
    <Sub delay={185}>ต่าง 1 ข้อ = 0.036 · n = 28 คือ noise ไม่ใช่นัยสำคัญ</Sub>
  </Scene>
);

const VARIANTS = [
  { k: "E0", n: "baseline 180 คำ", mrr: 0.882 },
  { k: "E1", n: "ลบ boilerplate + ตามประโยค", mrr: 0.893 },
  { k: "E2", n: "ตาราง markdown", mrr: 0.875 },
  { k: "E3", n: "E2 + context จาก LLM", mrr: 0.873 },
  { k: "E4", n: "parent-child", mrr: 0.889 },
];

export const Chunking: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Scene>
      <Headline>ลอง chunking 4 แบบ</Headline>
      <Sub delay={8}>hybrid MRR — แกนเริ่มที่ 0.80 เพื่อให้เห็นความต่าง</Sub>
      <div style={{ marginTop: 50 }}>
        {VARIANTS.map((v, i) => {
          const d = 25 + i * 18;
          const w = interpolate(frame, [d, d + 30], [0, (v.mrr - 0.8) / 0.12], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
          const op = interpolate(frame, [d - 6, d], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={v.k} style={{ opacity: op, display: "flex", alignItems: "center", gap: 28, marginBottom: 26 }}>
              <div style={{ width: 90, fontSize: 46, fontWeight: 700, color: i === 0 ? C.teal : C.text }}>{v.k}</div>
              <div style={{ width: 520, fontSize: 38, color: C.dim }}>{v.n}</div>
              <div style={{ width: 700, height: 44, background: C.panel, borderRadius: 8, overflow: "hidden" }}>
                <div style={{ width: `${w * 100}%`, height: "100%", background: i === 0 ? C.teal : C.blue }} />
              </div>
              <div style={{ fontSize: 44, fontWeight: 700 }}>{v.mrr.toFixed(3)}</div>
            </div>
          );
        })}
      </div>
      <Sub delay={130} color={C.amber}>ไม่มีแบบไหนชนะ baseline ชัดเจน — ต่างกันอยู่ในระดับ noise</Sub>
    </Scene>
  );
};

export const Failure: React.FC = () => {
  const frame = useCurrentFrame();
  const clash = interpolate(frame, [150, 175], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Scene>
      <Headline>กรณีล้มเหลว: A07</Headline>
      <Sub delay={8}>AIA CI Care คุ้มครองโรคร้ายแรงระยะรุนแรงกี่โรค?</Sub>
      <div style={{ display: "flex", gap: 56, marginTop: 36 }}>
        <Reveal delay={30} style={{ flex: 1 }}>
          <Card>
            <div style={{ fontSize: 38, color: C.dim }}>หน้า 1 ของโบรชัวร์</div>
            <div style={{ fontSize: 40, marginTop: 10 }}>"Cover 44 severe stage critical illnesses"</div>
            <div style={{ fontSize: 120, fontWeight: 700, lineHeight: 1.1, color: C.amber }}>44</div>
            <div style={{ fontSize: 38, color: C.amber }}>← โมเดลตอบตามนี้</div>
          </Card>
        </Reveal>
        <Reveal delay={70} style={{ flex: 1 }}>
          <Card>
            <div style={{ fontSize: 38, color: C.dim }}>หน้า 2 หัวตาราง</div>
            <div style={{ fontSize: 40, marginTop: 10 }}>"Severe Stage (40 Diseases / Treatment)"</div>
            <div style={{ fontSize: 120, fontWeight: 700, lineHeight: 1.1, color: C.blue }}>40</div>
            <div style={{ fontSize: 38, color: C.blue }}>← gold label ตามนี้</div>
          </Card>
        </Reveal>
      </div>
      <div style={{ opacity: clash, marginTop: 30 }}>
        <div style={{ fontSize: 52, fontWeight: 700, color: C.red }}>โบรชัวร์ขัดแย้งกันเอง — ไม่ใช่ hallucination</div>
        <div style={{ fontSize: 42, color: C.dim }}>ระบบยังไม่แจ้งความขัดแย้ง (งานต่อไป)</div>
      </div>
    </Scene>
  );
};

export const Outro: React.FC = () => (
  <Scene>
    <Headline>ข้อจำกัดที่ต้องรู้</Headline>
    <div style={{ marginTop: 40 }}>
      <Sub delay={14} color={C.text}>• eval เล็ก ปรับจูนบนชุดเดียวกัน ไม่มี held-out set</Sub>
      <Sub delay={30} color={C.text}>• ให้คะแนนด้วย keyword เป็นเพียง proxy</Sub>
      <Sub delay={46} color={C.text}>• เฉพาะโบรชัวร์ภาษาอังกฤษ · agent ยังไม่มี gold set</Sub>
    </div>
    <div style={{ marginTop: 80 }}>
      <Reveal delay={70}>
        <div style={{ fontSize: 56, fontWeight: 700, color: C.teal }}>github.com/Calvinkub/aia-insurance-rag</div>
      </Reveal>
    </div>
  </Scene>
);
