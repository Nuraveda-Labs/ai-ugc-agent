"""Variants engine — one brief × N hook angles → N HeyGen Video Agent prompts.

Today (Phase 2): expand a Brief into a list of (hook, prompt) pairs, one per
hook_angle in the brief. Caller fires them in parallel against HeyGen.

Tomorrow (Phase 2.5): score variants by (a) Whisper-checking the spoken
hook actually says what we asked for, (b) human approval via Discord ✅/❌,
(c) post-launch CPA pulled from Meta Ads Manager.
"""
from __future__ import annotations

from dataclasses import dataclass

from ugc.scripts.brief_loader import Brief
from ugc.scripts.prompt_builder import build_prompt


@dataclass
class Variant:
    index: int            # 1-based, for filenames + logs
    hook: str             # the hook line this variant leads with
    prompt: str           # the full HeyGen prompt
    target_seconds: int


def expand(
    brief: Brief,
    *,
    target_seconds: int = 25,
    limit: int | None = None,
) -> list[Variant]:
    """Return one Variant per hook_angle in the brief (capped by `limit`).

    The brief's hook_angles list IS the source of variant diversity —
    every other field stays identical so we're A/B-testing the hook
    cleanly without confounding.
    """
    hooks = brief.hook_angles[: limit] if limit else brief.hook_angles
    return [
        Variant(
            index=i + 1,
            hook=hook,
            prompt=build_prompt(brief=brief, hook=hook, target_seconds=target_seconds),
            target_seconds=target_seconds,
        )
        for i, hook in enumerate(hooks)
    ]
