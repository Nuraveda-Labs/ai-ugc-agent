#!/usr/bin/env python3
"""V11: Pexels stock + Remotion (kinetic captions + animated end card).

Per video:
  - Reuses Pexels clips + ElevenLabs VO from v10 (cached)
  - Whisper word-level timestamps -> caption JSON
  - Remotion renders final mp4 with TikTok-style word-by-word kinetic captions
    and a spring-animated URL end card
"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys

import httpx

ROOT = pathlib.Path(".")
V10 = ROOT / "output/ai-ugc-agent-pro/pexels-v10"
RUN = ROOT / "output/ai-ugc-agent-pro/remotion-v11"

VIDEOS = ["01_en", "01_hi", "03_en", "03_hi"]
ENDCARDS = {
    "01_en": {"line1": "grow.example.com", "line2": "Founder Stack — buy once, own forever"},
    "01_hi": {"line1": "grow.example.com/in", "line2": "Founder Stack — ek baar khareedo, hamesha tumhara"},
    "03_en": {"line1": "grow.example.com", "line2": "Recurring revenue. Yours forever."},
    "03_hi": {"line1": "grow.example.com/in", "line2": "Recurring revenue. Hamesha tumhara."},
}

def whisper_words(audio: pathlib.Path) -> list[dict]:
    """OpenAI Whisper API with word-level timestamps."""
    key = os.environ["OPENAI_API_KEY"]
    with open(audio, "rb") as f:
        r = httpx.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (audio.name, f, "audio/mpeg")},
            data={"model":"whisper-1","response_format":"verbose_json","timestamp_granularities[]":"word"},
            timeout=180,
        )
    r.raise_for_status()
    j = r.json()
    out = []
    for w in j.get("words", []):
        out.append({"text": w["word"].strip(), "startSec": float(w["start"]), "endSec": float(w["end"])})
    return out

def render_remotion(props_file: pathlib.Path, out_mp4: pathlib.Path) -> None:
    public_dir = str((ROOT / "output").resolve())
    cmd = ["npx", "remotion", "render", "remotion/index.tsx", "ugc",
           str(out_mp4), "--props", str(props_file),
           "--public-dir", public_dir]
    print(f"[remotion] -> {out_mp4.name}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    print(f"[remotion] done {out_mp4.name} ({out_mp4.stat().st_size//1024}KB)")

def main():
    RUN.mkdir(parents=True, exist_ok=True)
    # publicDir is ROOT/output; use paths relative to it
    OUTPUT = ROOT / "output"
    for slug in VIDEOS:
        clips = [str((V10 / f"{slug}_s{i}_norm.mp4").relative_to(OUTPUT)) for i in range(1, 6)]
        audio_rel = str((V10 / f"{slug}_vo.mp3").relative_to(OUTPUT))
        audio = V10 / f"{slug}_vo.mp3"
        # captions
        cap_file = RUN / f"{slug}_words.json"
        if not cap_file.exists():
            print(f"[whisper] {slug}")
            words = whisper_words(audio)
            cap_file.write_text(json.dumps(words, indent=2))
        else:
            words = json.loads(cap_file.read_text())
        props = {
            "clips": clips,
            "audioSrc": audio_rel,
            "captions": words,
            "endCard": ENDCARDS[slug],
        }
        props_file = RUN / f"{slug}_props.json"
        props_file.write_text(json.dumps(props))
        out = RUN / f"{slug}_master.mp4"
        render_remotion(props_file, out)

if __name__ == "__main__":
    main()
