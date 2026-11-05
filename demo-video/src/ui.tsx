import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, fontFamily } from "./theme";

export const Scene: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <AbsoluteFill style={{ backgroundColor: C.bg, fontFamily, color: C.text, padding: "100px 120px" }}>
    {children}
  </AbsoluteFill>
);

const ease = Easing.bezier(0.16, 1, 0.3, 1);

// Fades and rises in over `dur` frames, starting at `delay` frames.
export const Reveal: React.FC<{ delay?: number; dur?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  delay = 0,
  dur = 20,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        opacity: interpolate(frame, [delay, delay + dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }),
        translate: interpolate(frame, [delay, delay + dur], ["0px 40px", "0px 0px"], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }),
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Headline: React.FC<{ children: React.ReactNode; delay?: number }> = ({ children, delay = 0 }) => (
  <Reveal delay={delay}>
    <div style={{ fontSize: 96, fontWeight: 700, lineHeight: 1.25 }}>{children}</div>
  </Reveal>
);

export const Sub: React.FC<{ children: React.ReactNode; delay?: number; color?: string }> = ({ children, delay = 0, color = C.dim }) => (
  <Reveal delay={delay}>
    <div style={{ fontSize: 48, lineHeight: 1.45, color }}>{children}</div>
  </Reveal>
);

// Horizontal bar that grows to `value` (0..1) starting at `delay`.
export const Bar: React.FC<{ label: string; value: number; shown: string; color: string; delay: number; width?: number }> = ({
  label,
  value,
  shown,
  color,
  delay,
  width = 1000,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const grow = interpolate(frame, [delay, delay + 1.2 * fps], [0, value], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const op = interpolate(frame, [delay - 8, delay], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ opacity: op, display: "flex", alignItems: "center", gap: 32, marginBottom: 34 }}>
      <div style={{ width: 560, fontSize: 42, color: C.text }}>{label}</div>
      <div style={{ width, height: 54, background: C.panel, borderRadius: 10, overflow: "hidden" }}>
        <div style={{ width: `${grow * 100}%`, height: "100%", background: color, borderRadius: 10 }} />
      </div>
      <div style={{ fontSize: 52, fontWeight: 700, width: 130 }}>{shown}</div>
    </div>
  );
};

export const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ background: C.panel, border: `2px solid ${C.line}`, borderRadius: 24, padding: "36px 44px", ...style }}>{children}</div>
);
