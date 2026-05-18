"""Scene plan — split a Brief + variant into the 6-scene structure that the
HyperFrames composition template renders.

Why this exists:
  The Video Agent path collapses everything into one English prompt and
  hopes for the best. The HyperFrames path needs explicit scene records
  with start/duration/kind so the composition.html can be assembled
  deterministically. This module is the bridge between the brief schema
  and the composition template.

Scenes are either AVATAR (HeyGen renders the spoken clip) or OVERLAY
(the composition draws it from a HF block).

For the default 25-second target the layout is:

  Scene 1  [0-2s]    avatar    hook
  Scene 2  [2-4s]    overlay   pattern-interrupt — pain headline
  Scene 3  [4-11s]   avatar    pain restated
  Scene 4  [11-18s]  avatar    product reveal
  Scene 5  [18-22s]  overlay   social-proof — metrics
  Scene 6  [22-25s]  avatar    CTA + URL burn-in

When target_seconds != 25, durations rescale linearly so the structure
stays intact at any length.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ugc.scripts.brief_loader import Brief
from ugc.variants import Variant

SceneKind = str  # "avatar" | "overlay"


@dataclass
class Scene:
    index: int            # 1-based
    kind: SceneKind       # "avatar" | "overlay"
    start: float          # seconds
    duration: float       # seconds
    spoken_text: str = ""        # only for kind="avatar"
    block: str = ""              # only for kind="overlay" — HF block name
    block_props: dict = field(default_factory=dict)  # block-specific data
    burn_in_text: str = ""       # optional on-screen text overlay (e.g. CTA URL)

    @property
    def end(self) -> float:
        return round(self.start + self.duration, 3)


_BASE_TARGET = 25.0
_BASE_PLAN = [
    # (kind, base_start, base_duration)
    ("avatar", 0.0, 2.0),
    ("overlay", 2.0, 2.0),
    ("avatar", 4.0, 7.0),
    ("avatar", 11.0, 7.0),
    ("overlay", 18.0, 4.0),
    ("avatar", 22.0, 3.0),
]


def plan_scenes(
    *,
    brief: Brief,
    variant: Variant,
    target_seconds: float | None = None,
) -> list[Scene]:
    """Build the 6-scene plan for one variant.

    The base plan is 25s; pass `target_seconds` to scale linearly. Each
    scene's spoken text / overlay payload is filled from the brief.
    """
    target = float(target_seconds if target_seconds else variant.target_seconds)
    scale = target / _BASE_TARGET

    scaled = []
    for kind, base_start, base_duration in _BASE_PLAN:
        scaled.append((kind, round(base_start * scale, 3), round(base_duration * scale, 3)))

    # Fix any floating-point drift on the final scene's end so durations sum
    # exactly to target.
    last_kind, last_start, _last_dur = scaled[-1]
    scaled[-1] = (last_kind, last_start, round(target - last_start, 3))

    pain_oneline = " ".join(brief.audience.pain.split())
    pain_short = (pain_oneline[:80] + "…") if len(pain_oneline) > 80 else pain_oneline

    scenes: list[Scene] = []
    for i, (_kind, start, duration) in enumerate(scaled, start=1):
        if i == 1:
            scenes.append(Scene(
                index=i, kind="avatar", start=start, duration=duration,
                spoken_text=variant.hook,
            ))
        elif i == 2:
            scenes.append(Scene(
                index=i, kind="overlay", start=start, duration=duration,
                block="pattern-interrupt",
                block_props={
                    "headline": pain_short,
                    "subhead": brief.audience.who,
                },
            ))
        elif i == 3:
            scenes.append(Scene(
                index=i, kind="avatar", start=start, duration=duration,
                spoken_text=f"{brief.audience.who}. {pain_oneline}",
            ))
        elif i == 4:
            scenes.append(Scene(
                index=i, kind="avatar", start=start, duration=duration,
                spoken_text=f"{brief.product.name} — {brief.product.one_liner}.",
            ))
        elif i == 5:
            metrics = brief.metrics
            scenes.append(Scene(
                index=i, kind="overlay", start=start, duration=duration,
                block="social-proof",
                block_props={
                    "headline": metrics.headline if metrics else "Real results",
                    "label": metrics.label if metrics else "",
                },
            ))
        elif i == 6:
            scenes.append(Scene(
                index=i, kind="avatar", start=start, duration=duration,
                spoken_text=brief.cta.text,
                burn_in_text=brief.product.link,
            ))
        else:
            raise AssertionError(f"unexpected scene index {i}")
    return scenes


def avatar_scenes(scenes: list[Scene]) -> list[Scene]:
    """Filter helper — only the scenes that need a HeyGen avatar render."""
    return [s for s in scenes if s.kind == "avatar"]


def total_duration(scenes: list[Scene]) -> float:
    """Sum of all scene durations (== end of last scene)."""
    return scenes[-1].end if scenes else 0.0
