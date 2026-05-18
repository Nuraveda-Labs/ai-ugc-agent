#!/usr/bin/env python3
"""Regenerate scenes 03/04 via fal OmniHuman v1.5 (full body motion talking head).
Reuses founder_office_9x16.jpg + existing 03_vo.mp3 / 04_vo.mp3."""
from __future__ import annotations
import os, pathlib, sys, urllib.request

import fal_client

ROOT = pathlib.Path(".")
SCENES = ROOT / "output/glitch-ugc-pro/ai-marketing-stack/scenes"
ACTOR = ROOT / "assets/actors/founder_unsplash_9x16.jpg"
MODEL = "fal-ai/bytedance/omnihuman"

def run(n: str) -> None:
    img_url = fal_client.upload_file(str(ACTOR))
    audio_url = fal_client.upload_file(str(SCENES / f"{n}_vo.mp3"))
    print(f"[omnihuman] {n} submit", flush=True)
    result = fal_client.subscribe(
        MODEL,
        arguments={"image_url": img_url, "audio_url": audio_url},
        with_logs=True,
    )
    video = (result or {}).get("video") or {}
    url = video.get("url")
    if not url:
        print(f"[omnihuman] no url: {result!r}", file=sys.stderr); raise SystemExit(1)
    out = SCENES / f"{n}_raw.mp4"
    urllib.request.urlretrieve(url, out)
    print(f"[omnihuman] {n} -> {out} ({out.stat().st_size//1024} KB)")

def main() -> None:
    key = os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")
    if not key: raise SystemExit("FAL_API_KEY not set")
    os.environ["FAL_KEY"] = key
    for n in ("03", "04"):
        run(n)

if __name__ == "__main__":
    main()
