import {
  AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { z } from "zod";

const SCENE_SECONDS = 5;

export const ugcSchema = z.object({
  clips: z.array(z.string()),
  audioSrc: z.string(),
  // word-level captions: each {text, startSec, endSec}
  captions: z.array(
    z.object({ text: z.string(), startSec: z.number(), endSec: z.number() })
  ),
  endCard: z.object({ line1: z.string(), line2: z.string() }),
});
export type UgcProps = z.infer<typeof ugcSchema>;

const ActiveWord: React.FC<{ text: string; isActive: boolean; isPast: boolean }> = ({
  text, isActive, isPast,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = isActive ? spring({ frame, fps, config: { damping: 10, mass: 0.5 } }) * 0.2 + 1 : 1;
  return (
    <span
      style={{
        display: "inline-block",
        margin: "0 12px",
        transform: `scale(${scale})`,
        color: isActive ? "#7CFFB2" : isPast ? "#ffffff" : "#ffffff",
        opacity: isActive ? 1 : isPast ? 0.55 : 0.85,
        textShadow: "0 4px 24px rgba(0,0,0,0.95), 0 0 8px rgba(0,0,0,0.95)",
        fontWeight: 800,
      }}
    >
      {text}
    </span>
  );
};

const CaptionTrack: React.FC<{ captions: UgcProps["captions"] }> = ({ captions }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  // Show a window of ~3-5 words around the current spoken word
  const idx = captions.findIndex((c) => t >= c.startSec && t < c.endSec);
  if (idx === -1 && t < (captions[0]?.startSec ?? 0)) return null;
  const window = 4;
  const center = idx === -1 ? captions.findIndex((c) => c.startSec > t) - 1 : idx;
  const start = Math.max(0, center - 1);
  const end = Math.min(captions.length, start + window);
  const visible = captions.slice(start, end);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 320,
      }}
    >
      <div
        style={{
          fontFamily: "Inter, system-ui, sans-serif",
          fontSize: 78,
          color: "white",
          textAlign: "center",
          lineHeight: 1.1,
          maxWidth: "85%",
          padding: "20px 28px",
          background: "rgba(0,0,0,0.45)",
          borderRadius: 24,
          backdropFilter: "blur(8px)",
        }}
      >
        {visible.map((c, i) => {
          const realIdx = start + i;
          return (
            <ActiveWord
              key={realIdx}
              text={c.text}
              isActive={realIdx === idx}
              isPast={realIdx < idx}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const EndCard: React.FC<{ endCard: UgcProps["endCard"] }> = ({ endCard }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 12, mass: 0.6 } });
  const lineY = interpolate(enter, [0, 1], [80, 0]);
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  return (
    <AbsoluteFill style={{ background: "#0a0a0a" }}>
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: 24,
          fontFamily: "Inter, system-ui, sans-serif",
          color: "white",
          textAlign: "center",
          padding: 80,
          opacity,
          transform: `translateY(${lineY}px)`,
        }}
      >
        <div style={{ fontSize: 96, fontWeight: 900, letterSpacing: -2 }}>{endCard.line1}</div>
        <div style={{ fontSize: 44, color: "#7CFFB2", fontWeight: 600 }}>{endCard.line2}</div>
        <div style={{ marginTop: 60, fontSize: 30, opacity: 0.7 }}>Tap to learn more →</div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const UgcVideo: React.FC<UgcProps> = ({ clips, audioSrc, captions, endCard }) => {
  const { fps } = useVideoConfig();
  const sceneFrames = SCENE_SECONDS * fps;
  return (
    <AbsoluteFill style={{ background: "black" }}>
      {clips.map((src, i) => (
        <Sequence key={i} from={i * sceneFrames} durationInFrames={sceneFrames}>
          <OffthreadVideo
            src={staticFile(src)}
            startFrom={0}
            endAt={sceneFrames}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            muted
          />
        </Sequence>
      ))}
      <Sequence from={clips.length * sceneFrames}>
        <EndCard endCard={endCard} />
      </Sequence>
      <Audio src={staticFile(audioSrc)} />
      <CaptionTrack captions={captions} />
    </AbsoluteFill>
  );
};
