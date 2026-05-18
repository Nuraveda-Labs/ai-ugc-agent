#!/usr/bin/env python3
"""V6 render driven by brief.json. All-fal pipeline:
  - ElevenLabs TTS for all VO
  - fal seedance text-to-video for b-roll scenes
  - fal omnihuman (with prompt!) for talking-head scenes
"""
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, urllib.request

import fal_client
import httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/glitch-ugc-pro/ai-marketing-stack-v6"
SCENES = RUN / "scenes"
ELEVEN_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam
ELEVEN_MODEL = "eleven_turbo_v2_5"

def sh(cmd: list[str]) -> None:
    print("$", " ".join(cmd[:4]), "...", flush=True)
    subprocess.run(cmd, check=True)

async def tts(text: str, out_mp3: pathlib.Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}"
    body = {
        "text": text, "model_id": ELEVEN_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3},
    }
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(url, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept": "audio/mpeg"}, json=body)
        r.raise_for_status(); out_mp3.write_bytes(r.content)
    print(f"[tts] {out_mp3.name} {out_mp3.stat().st_size//1024}KB")

def seedance(scene: dict, out_mp4: pathlib.Path) -> None:
    print(f"[seedance] scene {scene['i']} submit", flush=True)
    result = fal_client.subscribe(
        scene["model"],
        arguments={
            "prompt": scene["prompt"],
            "aspect_ratio": "9:16",
            "duration": str(int(scene["duration_s"])),
            "resolution": scene.get("resolution","1080p"),
        },
        with_logs=True,
    )
    url = (result.get("video") or {}).get("url")
    if not url: raise SystemExit(f"no video url: {result}")
    urllib.request.urlretrieve(url, out_mp4)
    print(f"[seedance] -> {out_mp4} ({out_mp4.stat().st_size//1024}KB)")

def omnihuman(scene: dict, audio_mp3: pathlib.Path, actor: pathlib.Path, out_mp4: pathlib.Path) -> None:
    img_url = fal_client.upload_file(str(actor))
    audio_url = fal_client.upload_file(str(audio_mp3))
    print(f"[omnihuman] scene {scene['i']} submit", flush=True)
    result = fal_client.subscribe(
        scene["model"],
        arguments={
            "image_url": img_url,
            "audio_url": audio_url,
            "prompt": scene["prompt"],
            "resolution": "1080p",
        },
        with_logs=True,
    )
    url = (result.get("video") or {}).get("url")
    if not url: raise SystemExit(f"no video url: {result}")
    urllib.request.urlretrieve(url, out_mp4)
    print(f"[omnihuman] -> {out_mp4} ({out_mp4.stat().st_size//1024}KB)")

def mux(video: pathlib.Path, audio: pathlib.Path, out: pathlib.Path) -> None:
    sh(["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),
        "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k",
        "-shortest","-movflags","+faststart",str(out)])

async def main() -> None:
    SCENES.mkdir(parents=True, exist_ok=True)
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]
    brief = json.loads((RUN / "brief.json").read_text())
    actor = ROOT / brief["actor_image"]

    # 1) TTS for all 4
    await asyncio.gather(*[
        tts(s["vo"], SCENES / f"{s['i']:02d}_vo.mp3") for s in brief["scenes"]
    ])

    # 2) Render each scene
    for s in brief["scenes"]:
        n = f"{s['i']:02d}"
        raw = SCENES / f"{n}_raw.mp4"
        if s["engine"] == "fal-seedance":
            seedance(s, raw)
            # mux ElevenLabs VO under b-roll (fal seedance outputs silent video)
            tmp = SCENES / f"{n}_raw_audio.mp4"
            mux(raw, SCENES / f"{n}_vo.mp3", tmp)
            raw.unlink(); tmp.rename(raw)
        elif s["engine"] == "fal-omnihuman":
            omnihuman(s, SCENES / f"{n}_vo.mp3", actor, raw)
        print(f"[done] scene {n}")

    print("[v6] all 4 raw scenes ready")

if __name__ == "__main__":
    asyncio.run(main())
