import React from "react";
import { Audio } from "@remotion/media";
import { Sequence, interpolate, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Chunking, Failure, Outro, Pipeline, Problem, Results, Title } from "./scenes";
import audio from "./audio.json";
import { DemoScene } from "./DemoScene";

export const T = 15;
const FPS = 30;
const LEAD = 12; // frames of silence before the voice starts
const TAIL = 1.2; // seconds after the voice ends

const durations = audio as Record<string, number>;
const FADE = 6; // frames of volume ramp at each end of a clip, so transitions stay silent

// `frames` is the minimum length the animation needs; a scene grows to fit its voice-over clip.
const BASE = [
  { name: "Title", clip: "title", frames: 150, el: <Title /> },
  { name: "Problem", clip: "problem", frames: 210, el: <Problem /> },
  { name: "Pipeline", clip: "pipeline", frames: 300, el: <Pipeline /> },
  { name: "Demo", clip: "demo-scene", frames: Math.ceil(45.03 * FPS), el: <DemoScene /> },
  { name: "Results", clip: "results", frames: 300, el: <Results /> },
  { name: "Chunking", clip: "chunking", frames: 240, el: <Chunking /> },
  { name: "Failure", clip: "failure", frames: 300, el: <Failure /> },
  { name: "Outro", clip: "outro", frames: 210, el: <Outro /> },
];

export const SCENES = BASE.map((s) => {
  const d = durations[s.clip];
  return { ...s, frames: d ? Math.max(s.frames, Math.ceil((d + TAIL) * FPS) + LEAD) : s.frames, hasClip: d !== undefined };
});
export const TOTAL = SCENES.reduce((a, s) => a + s.frames, 0) - T * (SCENES.length - 1);

export const Motion: React.FC = () => (
  <TransitionSeries>
    {SCENES.flatMap((s, i) => [
      <TransitionSeries.Sequence key={s.name} name={s.name} durationInFrames={s.frames}>
        {s.el}
        {s.hasClip ? (
          <Sequence from={LEAD} name={`Voice ${s.clip}`}>
            <Audio
              src={staticFile(`audio/${s.clip}.wav`)}
              volume={(f) =>
                interpolate(f, [0, FADE, Math.round(durations[s.clip] * FPS) - FADE, Math.round(durations[s.clip] * FPS)], [0, 1, 1, 0], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })
              }
            />
          </Sequence>
        ) : null}
      </TransitionSeries.Sequence>,
      ...(i < SCENES.length - 1
        ? [<TransitionSeries.Transition key={`t${i}`} presentation={fade()} timing={linearTiming({ durationInFrames: T })} />]
        : []),
    ])}
  </TransitionSeries>
);
