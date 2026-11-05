import { Composition } from "remotion";
import { Motion, TOTAL } from "./Motion";

export const RemotionRoot: React.FC = () => (
  <Composition id="AiaDemo" component={Motion} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
);
