import React from "react";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { Chunking, Failure, Outro, Pipeline, Problem, Results, Title } from "./scenes";

export const T = 15;
export const SCENES = [
  { name: "Title", frames: 150, el: <Title /> },
  { name: "Problem", frames: 210, el: <Problem /> },
  { name: "Pipeline", frames: 300, el: <Pipeline /> },
  { name: "Results", frames: 300, el: <Results /> },
  { name: "Chunking", frames: 240, el: <Chunking /> },
  { name: "Failure", frames: 300, el: <Failure /> },
  { name: "Outro", frames: 210, el: <Outro /> },
];
export const TOTAL = SCENES.reduce((a, s) => a + s.frames, 0) - T * (SCENES.length - 1);

export const Motion: React.FC = () => (
  <TransitionSeries>
    {SCENES.flatMap((s, i) => [
      <TransitionSeries.Sequence key={s.name} name={s.name} durationInFrames={s.frames}>
        {s.el}
      </TransitionSeries.Sequence>,
      ...(i < SCENES.length - 1
        ? [<TransitionSeries.Transition key={`t${i}`} presentation={fade()} timing={linearTiming({ durationInFrames: T })} />]
        : []),
    ])}
  </TransitionSeries>
);
