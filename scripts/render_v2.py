#!/usr/bin/env python3
"""V2 render: ElevenLabs VO + Mirage talking-head for 03/04, fal b-roll for 01/02."""
from __future__ import annotations
import asyncio, os, pathlib, subprocess, sys, urllib.request

import httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/ai-marketing-stack"
SCENES = RUN / "scenes"
ELEVEN_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam — confident male
ELEVEN_MODEL = "eleven_turbo_v2_5"

SCRIPTS = {
    "01": "Bleeding four hundred eighty a month on SaaS tools you barely use?",
    "02": "AI Marketing Stack. Six production AI agents. One command. Yours forever.",
    "03": "We cancelled almost five hundred a month, and resell these agents at three thousand each.",
    "04": "Four ninety-nine. One time. Yours forever. Link below.",
}

def sh(cmd: list[str]) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

async def tts(text: str, out_mp3: pathlib.Path) -> None:
    key = os.environ["ELEVENLABS_API_KEY"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_VOICE}"
    body = {
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3},
    }
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(url, headers={"xi-api-key": key, "accept": "audio/mpeg"}, json=body)
        r.raise_for_status()
        out_mp3.write_bytes(r.content)
    print(f"[tts] {out_mp3.name} {out_mp3.stat().st_size//1024} KB")

async def mirage_clip(audio_path: pathlib.Path, out_mp4: pathlib.Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from ugc.integrations.mirage import MirageClient
    actor = ROOT / "assets/actors/founder_office_9x16.jpg"
    m = MirageClient()
    await m.audio_to_clip(image_path=actor, audio_path=audio_path, out_path=out_mp4)
    print(f"[mirage] {out_mp4.name} {out_mp4.stat().st_size//1024} KB")

def mux_video_audio(video: pathlib.Path, audio: pathlib.Path, out: pathlib.Path) -> None:
    sh(["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),
        "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k",
        "-shortest","-movflags","+faststart",str(out)])

async def main() -> None:
    SCENES.mkdir(parents=True, exist_ok=True)
    # 1) ElevenLabs VO for all 4
    await asyncio.gather(*[tts(SCRIPTS[n], SCENES / f"{n}_vo.mp3") for n in ["01","02","03","04"]])

    # 2) Mux fal b-roll + VO for 01,02 → new *_raw_audio.mp4 (overwrite raw with audio version)
    for n in ["01","02"]:
        v = SCENES / f"{n}_raw.mp4"
        a = SCENES / f"{n}_vo.mp3"
        out = SCENES / f"{n}_raw_audio.mp4"
        mux_video_audio(v, a, out)
        # replace raw
        (SCENES / f"{n}_raw.mp4").unlink()
        out.rename(SCENES / f"{n}_raw.mp4")

    # 3) Mirage audio_to_clip for 03,04 (replaces HeyGen)
    await asyncio.gather(
        mirage_clip(SCENES / "03_vo.mp3", SCENES / "03_raw.mp4"),
        mirage_clip(SCENES / "04_vo.mp3", SCENES / "04_raw.mp4"),
    )

    print("[done] all 4 raw scenes regenerated with audio")

if __name__ == "__main__":
    asyncio.run(main())
