#!/usr/bin/env python3
"""Generate a UGC-style founder portrait via fal flux-pro for Mirage actor reference."""
from __future__ import annotations
import os, pathlib, urllib.request, sys

import fal_client

OUT = pathlib.Path("./assets/actors/founder_office_9x16.jpg")

PROMPT = (
    "Photorealistic vertical 9:16 selfie-style portrait of a 30-something male indie tech founder, "
    "short dark hair, light beard, casual heather-gray t-shirt, looking directly at camera, "
    "warm natural daylight from a window on the left, modern minimalist home office background "
    "with a soft-focus wooden desk, laptop, plant, bookshelf, and warm tungsten lamp, "
    "shallow depth of field bokeh, friendly approachable expression, smartphone front-camera aesthetic, "
    "high detail skin texture, no text, no logos"
)

def main() -> int:
    key = os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")
    if not key:
        print("FAL_API_KEY not set", file=sys.stderr); return 2
    os.environ["FAL_KEY"] = key
    print("[flux] submit", flush=True)
    result = fal_client.subscribe(
        "fal-ai/flux-pro/v1.1",
        arguments={
            "prompt": PROMPT,
            "image_size": {"width": 1080, "height": 1920},
            "num_images": 1,
            "enable_safety_checker": True,
        },
        with_logs=False,
    )
    img = (result or {}).get("images", [{}])[0]
    url = img.get("url")
    if not url:
        print(f"no url: {result!r}", file=sys.stderr); return 1
    print(f"[flux] download {url}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, OUT)
    print(f"[flux] wrote {OUT} ({OUT.stat().st_size//1024} KB)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
