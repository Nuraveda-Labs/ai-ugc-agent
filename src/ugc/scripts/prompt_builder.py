"""Convert a Brief + one hook → a HeyGen Video Agent prompt optimized for
production-grade UGC ads.

Why this is its own module:
  HeyGen's Video Agent does scene planning internally — but the QUALITY
  of its output depends almost entirely on how the prompt is structured.
  A vague prompt → corporate explainer. A structured prompt with
  format spec + scene-by-scene direction + visual cues + spoken-line
  hints → a real ad with cuts, overlays, and pattern interrupts.

  This module emits two artifacts from one brief+hook:

    build_prompt_json(...) -> dict   — the canonical structured brief
                                       (audit trail; same shape both pipelines consume).
    build_prompt(...)      -> str    — Video Agent text prompt that
                                       embeds the JSON inline as the
                                       single source of truth.

  Both pipelines (`make-from-brief` via /v3/video-agents and
  `compose-from-brief` via per-scene /v3/videos) write the JSON next to
  the rendered MP4 so we can diff/iterate on what we asked for.

Reference structure based on what works in vertical short-form ads:

  Scene 1 (0-2s)    Hook — bold, specific, contrarian or curiosity-bait
  Scene 2 (2-4s)    Pattern interrupt — sudden visual change (UI screen,
                    chart, before/after, the actual product surface)
  Scene 3 (4-10s)   Pain framing — concrete, named scenario the viewer
                    recognizes; creator delivers in selfie-style
  Scene 4 (10-18s)  Solution reveal — product introduced naturally,
                    with one specific data point or screen element
  Scene 5 (18-22s)  Social proof / specificity — real number, real name,
                    real screen
  Scene 6 (22-28s)  CTA — direct ask, low friction, urgency hint
"""
from __future__ import annotations

import json
from dataclasses import asdict

from ugc.scripts.brief_loader import Brief

PROMPT_SCHEMA_VERSION = "ai-ugc-agent.prompt.v1"

_VOICE_DIRECTION = {
    "confident-operator": (
        "Confident operator energy — speaks like someone who has shipped this thing and "
        "ran the spend, not like a salesperson. Crisp, direct, occasionally dry. Makes "
        "specific factual claims about the dashboard / the screens / the numbers."
    ),
    "scrappy-founder": (
        "Scrappy-founder energy — speaks like someone who built this on weekends with "
        "AI tools, not like a corporate spokesperson. Casual, slightly self-deprecating, "
        "concrete. Mentions specific tools and tradeoffs."
    ),
    "analyst-explainer": (
        "Analyst-explainer energy — speaks like someone who pulls dashboards for a living. "
        "Technical, evidence-led, breaks problems down with named UI elements."
    ),
}

_PACING_DIRECTION = {
    "fast": "Aggressive cuts every 2-4 seconds. No scene lingers.",
    "conversational": "Slower cuts every 4-6 seconds. Fewer total scenes.",
}

_HARD_RULES = [
    "Avatar must look like a real DTC operator / tech founder, not a corporate spokesperson.",
    "ZERO marketing-speak: no 'unleash', 'transform', 'revolutionize', 'powerful', "
    "'seamless', 'game-changing'.",
    "ZERO engagement-bait questions ('what do you think?', 'curious if you've tried').",
    "ZERO exclamation closers. End on a beat.",
    "Burn the CTA URL/handle on screen during the final scene.",
    "Vertical 9:16 1080x1920. No horizontal letterbox / pillarbox.",
]


def _scene_plan_for_prompt(*, brief: Brief, hook: str, target_seconds: int) -> list[dict]:
    """Scene plan as plain dicts, mirrored from ugc.scenes but written
    in the prompt-facing vocabulary (visual_direction is creative, not a
    HF block name).
    """
    s4_start = 4 + (target_seconds - 4) // 3
    s5_start = target_seconds - 6
    s6_start = target_seconds - 3
    return [
        {
            "index": 1,
            "label": "HOOK",
            "start_s": 0,
            "end_s": 2,
            "kind": "avatar",
            "spoken_text": hook,
            "visual_direction": (
                "Tight close-up on the creator delivering the hook in a single beat. "
                "Strong eye contact with camera. Frame should feel slightly raw / unpolished."
            ),
            "framing": "selfie close-up",
            "on_screen_text": None,
        },
        {
            "index": 2,
            "label": "PATTERN_INTERRUPT",
            "start_s": 2,
            "end_s": 4,
            "kind": "overlay",
            "spoken_text": None,
            "visual_direction": (
                "Sudden cut to a mockup of the relevant product UI / dashboard / screen "
                "where the pain happens. Animated text overlay flashes the most damning "
                "piece of data. No spoken voiceover here — let the visual breathe."
            ),
            "framing": "full-screen UI mockup",
            "on_screen_text": "(damning specific number / UI element name from the pain)",
        },
        {
            "index": 3,
            "label": "PAIN_FRAMING",
            "start_s": 4,
            "end_s": s4_start,
            "kind": "avatar",
            "spoken_text": None,  # agent writes — direction below tells it what to say
            "visual_direction": (
                "Back to the creator selfie-style. They name the SPECIFIC scenario from "
                "PAIN with concrete language — the actual platform, the actual UI element, "
                "the actual decision the viewer faces."
            ),
            "framing": "selfie medium",
            "on_screen_text": None,
        },
        {
            "index": 4,
            "label": "SOLUTION_REVEAL",
            "start_s": s4_start,
            "end_s": s5_start,
            "kind": "avatar",
            "spoken_text": brief.product.one_liner,
            "visual_direction": (
                f"The creator introduces {brief.product.name}. Show ONE concrete piece "
                "of the product (a UI screen, a result panel, a specific output) — "
                "not a generic screenshot."
            ),
            "framing": "selfie medium with product cutaway",
            "on_screen_text": None,
        },
        {
            "index": 5,
            "label": "SOCIAL_PROOF",
            "start_s": s5_start,
            "end_s": s6_start,
            "kind": "overlay",
            "spoken_text": None,
            "visual_direction": (
                "ONE specific data point with a number. Not 'increased ROAS' — the actual "
                "ratio (e.g. '1.67× → 4.1×'). Animated overlay graphic on top of a screen capture."
            ),
            "framing": "data-overlay on screen capture",
            "on_screen_text": "(specific headline metric)",
        },
        {
            "index": 6,
            "label": "CTA",
            "start_s": s6_start,
            "end_s": target_seconds,
            "kind": "avatar",
            "spoken_text": brief.cta.text,
            "visual_direction": (
                "Creator delivers the CTA. Quiet, confident sign-off — no exclamation. "
                "Burn the URL/handle on screen as a text overlay during the spoken CTA."
            ),
            "framing": "selfie close-up",
            "on_screen_text": brief.product.link or None,
        },
    ]


def build_prompt_json(
    *,
    brief: Brief,
    hook: str,
    target_seconds: int = 25,
) -> dict:
    """Return the canonical structured prompt as a JSON-serializable dict.

    Both pipelines write this to disk as `variant_NN.brief.json` and feed
    it as input to whatever HeyGen surface they call. For the Video Agent
    path we also embed it inside the text prompt verbatim.
    """
    voice_direction = _VOICE_DIRECTION.get(
        brief.style.voice, _VOICE_DIRECTION["confident-operator"],
    )
    pacing_direction = _PACING_DIRECTION.get(
        brief.style.pacing, _PACING_DIRECTION["fast"],
    )

    return {
        "schema": PROMPT_SCHEMA_VERSION,
        "hook": hook,
        "format": {
            "aspect_ratio": "9:16",
            "width": 1080,
            "height": 1920,
            "duration_seconds": target_seconds,
            "fps": 30,
            "platform_targets": ["meta_reels", "tiktok", "ig_reels"],
            "aesthetic": (
                "Real-creator UGC aesthetic — looks like the person filmed it on their "
                "iPhone. NOT a corporate explainer with a static talking head. NOT an "
                "animated whiteboard. Multiple scenes with cuts."
            ),
        },
        "brief": {
            "product": asdict(brief.product),
            "audience": asdict(brief.audience),
            "cta": asdict(brief.cta),
        },
        "voice": {
            "preset": brief.style.voice,
            "direction": voice_direction,
            "tone": brief.style.tone or None,
        },
        "pacing": {
            "preset": brief.style.pacing,
            "direction": pacing_direction,
        },
        "visuals": {
            "background_color": brief.visuals.background_color,
            "accent_color": brief.visuals.accent_color,
            "metrics_headline": brief.metrics.headline if brief.metrics else None,
            "metrics_label": brief.metrics.label if brief.metrics else None,
        },
        "scenes": _scene_plan_for_prompt(
            brief=brief, hook=hook, target_seconds=target_seconds,
        ),
        "hard_rules": _HARD_RULES,
    }


def build_prompt(
    *,
    brief: Brief,
    hook: str,
    target_seconds: int = 25,
) -> str:
    """Return the full prompt to hand HeyGen Video Agent for ONE variant.

    The prompt is a thin English wrapper around the canonical JSON brief
    so the Video Agent has one source of truth (timing, scene direction,
    voice, hard rules) and we can diff/iterate on the JSON without
    rewriting prose.
    """
    payload = build_prompt_json(
        brief=brief, hook=hook, target_seconds=target_seconds,
    )
    payload_json = json.dumps(payload, indent=2, ensure_ascii=False)

    return (
        f"Produce a {target_seconds}-second vertical 9:16 UGC-style ad for "
        f"{brief.product.name}. The full creative brief is the JSON document "
        "below. Treat it as the single source of truth: timing, scene-by-scene "
        "direction, voice, pacing, visuals, and hard rules. Do not deviate from "
        "the durations or the hard_rules.\n\n"
        "```json\n"
        f"{payload_json}\n"
        "```\n\n"
        "Render the final ad as a single MP4 honoring the scenes array in order."
    )
