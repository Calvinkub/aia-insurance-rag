import React from "react";
import { Video } from "@remotion/media";
import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import timeline from "./demo_timeline.json";
import { C, fontFamily } from "./theme";

const CAPTIONS: { key: "demo1" | "demo2" | "demo3" | "demo4"; text: string; color: string }[] = [
  { key: "demo1", text: "1 · คำถามที่มีคำตอบ → citation ขึ้นสถานะตรวจแล้ว", color: C.teal },
  { key: "demo2", text: "2 · คำถามที่ไม่มีในเอกสาร → ปฏิเสธ ไม่เดา", color: C.amber },
  { key: "demo3", text: "3 · Agent เรียก tool ทีละขั้น", color: C.blue },
  { key: "demo4", text: "4 · กรณีล้มเหลว: ตอบ 44 แต่ตารางหน้า 2 บอก 40", color: C.red },
];

const Caption: React.FC<{ text: string; color: string; from: number; to: number }> = ({ text, color, from, to }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [from, from + 10, to - 10, to], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const y = interpolate(frame, [from, from + 14], [24, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  return (
    <div
      style={{
        position: "absolute", left: 120, right: 120, bottom: 70, opacity: o, translate: `0px ${y}px`,
        background: "rgba(11,18,32,0.92)", border: `3px solid ${color}`, borderRadius: 18, padding: "18px 32px",
        fontFamily, fontSize: 46, fontWeight: 700, color: C.text,
      }}
    >
      {text}
    </div>
  );
};

export const DemoScene: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: "#ffffff" }}>
      <Video src={staticFile("demo.mp4")} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      {CAPTIONS.map((c) => (
        <Caption key={c.key} text={c.text} color={c.color} from={Math.round(timeline[c.key].start * fps)} to={Math.round(timeline[c.key].end * fps) + 30} />
      ))}
    </AbsoluteFill>
  );
};
