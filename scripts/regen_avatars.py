#!/usr/bin/env python3
"""Regenerate scenes 03/04 via Mirage with the new founder_office actor.
Reuses existing 03_vo.mp3 / 04_vo.mp3 — does not retrigger ElevenLabs."""
from __future__ import annotations
import asyncio, pathlib, sys

ROOT = pathlib.Path(".")
SCENES = ROOT / "output/ai-ugc-agent-pro/ai-marketing-stack/scenes"
ACTOR = ROOT / "assets/actors/founder_office_9x16.jpg"
sys.path.insert(0, str(ROOT / "src"))
from ugc.integrations.mirage import MirageClient

async def one(n: str) -> None:
    m = MirageClient()
    await m.audio_to_clip(
        image_path=ACTOR,
        audio_path=SCENES / f"{n}_vo.mp3",
        out_path=SCENES / f"{n}_raw.mp4",
    )
    print(f"[mirage] {n} done")

async def main() -> None:
    await asyncio.gather(one("03"), one("04"))

if __name__ == "__main__":
    asyncio.run(main())
