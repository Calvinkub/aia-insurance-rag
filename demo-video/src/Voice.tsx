import React from "react";
import { Audio } from "@remotion/media";
import { Sequence, interpolate, staticFile, useVideoConfig } from "remotion";
import audio from "./audio.json";

const durations = audio as Record<string, number>;
const FADE = 6; // frames of volume ramp at each end of a clip, so transitions stay silent

// Plays public/audio/<clip>.wav starting `from` frames into the parent, with a short fade in and out.
export const Voice: React.FC<{ clip: string; from: number }> = ({ clip, from }) => {
  const { fps } = useVideoConfig();
  const len = Math.round(durations[clip] * fps);
  return (
    <Sequence from={from} name={`Voice ${clip}`}>
      <Audio
        src={staticFile(`audio/${clip}.wav`)}
        volume={(f) => interpolate(f, [0, FADE, len - FADE, len], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}
      />
    </Sequence>
  );
};
