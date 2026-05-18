import { registerRoot, Composition } from "remotion";
import { UgcVideo, ugcSchema } from "./UgcVideo";

const FPS = 30;

const Root: React.FC = () => (
  <Composition
    id="ugc"
    component={UgcVideo}
    durationInFrames={FPS * 30}
    fps={FPS}
    width={1080}
    height={1920}
    schema={ugcSchema}
    defaultProps={{
      clips: [],
      audioSrc: "",
      captions: [],
      endCard: { line1: "grow.example.com", line2: "Founder Stack — yours forever" },
    }}
    calculateMetadata={({ props }) => {
      // total duration = sum of clips (each 5s) + 5s end card
      const totalSec = (props.clips.length + 1) * 5;
      return { durationInFrames: Math.round(totalSec * FPS), props };
    }}
  />
);

registerRoot(Root);
