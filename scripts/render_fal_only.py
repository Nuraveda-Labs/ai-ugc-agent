#!/usr/bin/env python3
"""All-fal pipeline: regenerate scenes 03/04 talking head via fal sync-lipsync.
Reuses existing 03_vo.mp3 / 04_vo.mp3 and assets/actors/founder_office_9x16.jpg.
"""
from __future__ import annotations
import asyncio, os, pathlib, subprocess, sys, urllib.request

import fal_client

ROOT = pathlib.Path(".")
SCENES = ROOT / "output/glitch-ugc-pro/ai-marketing-stack/scenes"
ACTOR = ROOT / "assets/actors/founder_office_9x16.jpg"
LIPSYNC_MODEL = "fal-ai/sync-lipsync"

def upload(path: pathlib.Path) -> str:
    return fal_client.upload_file(str(path))

def still_to_video(image: pathlib.Path, audio_mp3: pathlib.Path, out: pathlib.Path) -> None:
    dur = subprocess.check_output([
        "ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0", str(audio_mp3)
    ]).decode().strip()
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-loop","1","-i",str(image),"-t",dur,
        "-c:v","libx264","-pix_fmt","yuv420p","-r","30","-vf","scale=1080:1920","-an",
        str(out),
    ], check=True)

def lipsync_one(n: str) -> None:
    audio_path = SCENES / f"{n}_vo.mp3"
    still_video = SCENES / f"{n}_still.mp4"
    still_to_video(ACTOR, audio_path, still_video)
    video_url = upload(still_video)
    audio_url = upload(audio_path)
    print(f"[fal-lipsync] {n} submit", flush=True)
    result = fal_client.subscribe(
        LIPSYNC_MODEL,
        arguments={
            "video_url": video_url,
            "audio_url": audio_url,
            "model": "lipsync-1.9.0-beta",
        },
        with_logs=True,
    )
    video = (result or {}).get("video") or {}
    url = video.get("url")
    if not url:
        print(f"[fal-lipsync] {n} no url: {result!r}", file=sys.stderr); raise SystemExit(1)
    out = SCENES / f"{n}_raw.mp4"
    urllib.request.urlretrieve(url, out)
    print(f"[fal-lipsync] {n} -> {out} ({out.stat().st_size//1024} KB)")

def main() -> None:
    key = os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")
    if not key: raise SystemExit("FAL_API_KEY not set")
    os.environ["FAL_KEY"] = key
    for n in ("03", "04"):
        lipsync_one(n)

if __name__ == "__main__":
    main()
