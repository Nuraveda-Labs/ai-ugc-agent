#!/usr/bin/env python3
"""V15: 2 Hinglish ads for India market.
  - Voice: ElevenLabs Rahul S (Hindi conversational male)
  - Scene 1: Indian founder portrait, Ken Burns zoom (no lip-sync)
  - Scenes 2-5: Pexels real stock footage
  - Scene 6: Animated URL end card
  - Captions: Hinglish in Roman script, hand-authored, evenly timed
  - No fal.ai usage. Composition via Remotion (kinetic captions).
"""
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys

import httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/india-v15"
ACTOR = ROOT / "assets/actors/founder_indian_9x16.jpg"

VOICE_ID = "PCh1EG2epbGwiFQ8qcP5"  # Rehan — young Hindi male, social media tuned
ELEVEN_MODEL = "eleven_multilingual_v2"

# 2 angles, Hinglish-only, captions in Roman script
VIDEOS = {
    "a6_not_engineer": {
        "vo": (
            "Main engineer nahi hu. Maine multi-tenant AI agent ship kar diya — "
            "paying client ke liye. "
            "Claude ke saath vibe-code seekha tha. But har production attempt mein "
            "auth aur multi-tenant pe phas jata tha. "
            "Founder stack production parts handle karta hai. Main brand parts handle "
            "karta hu. Saath mein deploy ho jata hai. "
            "Client samajh raha hai main engineer hu. Maine sirf ek config file rename ki thi. "
            "Vibe-code kar lete ho, ship nahi kar paate? "
            "example dot com slash in dekho."
        ),
        "captions": [
            "Main engineer nahi hu.",
            "Multi-tenant AI agent",
            "ship kar diya — paying client ke liye.",
            "Claude se vibe-code seekha tha.",
            "Production attempt pe",
            "auth aur multi-tenant pe",
            "phas jata tha.",
            "Founder stack production",
            "parts handle karta hai.",
            "Main sirf brand parts.",
            "Saath mein deploy.",
            "Client samajh raha hai",
            "main engineer hu.",
            "Maine ek config file rename ki thi.",
            "Vibe-code karte ho,",
            "ship nahi kar paate?",
            "→ grow.example.com/in",
        ],
        "pexels_queries": [
            # scene 1 is the actor portrait, scenes 2-5 are pexels
            "indian developer laptop home office working coding",
            "github code editor screen dark theme",
            "saas dashboard ui multi-tenant admin panel",
            "web application launch celebrating success",
        ],
        "endcard": {"line1": "grow.example.com/in", "line2": "Founder Stack — engineer banne ki zaroorat nahi"},
    },
    "a7_voice_cod": {
        "vo": (
            "Mere D2C client ke COD calls ab AI handle karta hai — "
            "Hindi mein, teen rupay per call. "
            "Sab imported voice tools corporate English bolte hain. "
            "Tier-2, Tier-3 customers ko samajh hi nahi aata. "
            "Founder stack mein voice agent hai — LiveKit aur Sarvam. "
            "Hindi, Punjabi, Tamil — dus Indian languages. "
            "Real call duration ek minute. Cost teen rupay. "
            "Ek mid-volume merchant ka teen din mein bundle paid back. "
            "Indian D2C ke liye banaya hai — "
            "example dot com slash in."
        ),
        "captions": [
            "Mere D2C client ke COD calls",
            "AI handle karta hai.",
            "Hindi mein. ₹3 per call.",
            "Imported voice tools",
            "corporate English bolte hain.",
            "Tier-2/3 ko",
            "samajh nahi aata.",
            "Founder stack ka voice agent —",
            "LiveKit + Sarvam.",
            "Hindi, Punjabi, Tamil.",
            "10 Indian languages.",
            "Call duration: 1 minute.",
            "Cost: ₹3 per call.",
            "Mid-volume merchant —",
            "3 din mein bundle paid back.",
            "Indian D2C ke liye banaya hai.",
            "→ grow.example.com/in",
        ],
        "pexels_queries": [
            "indian small business owner shopify dashboard mobile",
            "customer service call center phone agent",
            "voice waveform audio recording microphone",
            "delivery package courier indian street",
        ],
        "endcard": {"line1": "grow.example.com/in", "line2": "Voice agent for Indian D2C — ₹3/call"},
    },
}

# ------------ helpers ------------

async def tts(voice_id, text, out):
    body = {"text": text, "model_id": ELEVEN_MODEL,
            "voice_settings": {"stability": 0.32, "similarity_boost": 0.78, "style": 0.45, "use_speaker_boost": True}}
    async with httpx.AsyncClient(timeout=240) as c:
        r = await c.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                         headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept":"audio/mpeg"}, json=body)
        r.raise_for_status(); out.write_bytes(r.content)
    print(f"[tts] {out.name} {out.stat().st_size//1024}KB")

def audio_dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode().strip())

def pexels_search(query, key):
    url = f"https://api.pexels.com/videos/search?query={query.replace(' ', '+')}&orientation=portrait&per_page=15&size=medium"
    r = httpx.get(url, headers={"Authorization": key}, timeout=60); r.raise_for_status()
    return r.json().get("videos", [])

def pick_best_file(video):
    portraits = [f for f in video["video_files"] if f.get("width",0) < f.get("height",0)]
    if not portraits: return None
    return sorted(portraits, key=lambda f: (abs(f.get("width",0)-1080), -f.get("width",0)))[0]

def fetch_clip(query, key, out, min_dur=5):
    vids = pexels_search(query, key)
    candidates = [v for v in vids if v.get("duration",0) >= min_dur] or vids
    if not candidates: raise RuntimeError(f"no Pexels: {query}")
    v = candidates[0]; f = pick_best_file(v) or v["video_files"][0]
    print(f"[pexels] {out.name} <- id={v['id']} {f.get('width')}x{f.get('height')}")
    with httpx.stream("GET", f["link"], follow_redirects=True, timeout=120,
                      headers={"User-Agent":"Mozilla/5.0 GlitchGrowUGC/1.0"}) as r:
        r.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in r.iter_bytes(64*1024): fh.write(chunk)

def make_kenburns_clip(image, out, dur=5):
    """Static portrait → Ken Burns slow zoom-in 9:16."""
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-loop","1","-i",str(image),"-t",str(dur),
        "-vf",
        f"scale=1620:2880,zoompan=z='min(zoom+0.0008,1.15)':d={dur*30}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,setsar=1",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(out)
    ], check=True)

def normalize_clip(src, dst, dur=5):
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-i",str(src),"-t",str(dur),
        "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(dst)
    ], check=True)

# ------------ whisper word-level for kinetic captions (use OpenAI but FORCE our text) ------------
# Since the captions are Hinglish in Roman script (which Whisper would mishandle), we
# evenly time the hand-authored caption phrases across audio_dur instead of running whisper.

def words_evenly_timed(captions: list[str], total_s: float) -> list[dict]:
    """Treat each caption phrase as a 'word' for the kinetic caption renderer."""
    n = len(captions); chunk = total_s / n
    return [{"text": c, "startSec": i*chunk, "endSec": (i+1)*chunk - 0.05} for i, c in enumerate(captions)]

def render_remotion(props_file, out_mp4):
    public_dir = str((ROOT / "output").resolve())
    cmd = ["npx", "remotion", "render", "remotion/index.tsx", "ugc",
           str(out_mp4), "--props", str(props_file), "--public-dir", public_dir]
    print(f"[remotion] -> {out_mp4.name}")
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    print(f"[remotion] done {out_mp4.name} ({out_mp4.stat().st_size//1024}KB)")

# ------------ main ------------

async def main():
    RUN.mkdir(parents=True, exist_ok=True)
    pexels_key = os.environ["PEXELS_API_KEY"]
    OUTPUT = ROOT / "output"

    for slug, v in VIDEOS.items():
        # 1) TTS
        vo = RUN / f"{slug}_vo.mp3"
        if not (vo.exists() and vo.stat().st_size > 5_000):
            await tts(VOICE_ID, v["vo"], vo)

        # 2) Scene 1 = founder portrait Ken Burns
        s1 = RUN / f"{slug}_s1_norm.mp4"
        if not s1.exists():
            make_kenburns_clip(ACTOR, s1, dur=5)
            print(f"[kenburns] {s1.name}")

        # 3) Scenes 2-5 = Pexels stock
        for i, q in enumerate(v["pexels_queries"], 2):
            raw = RUN / f"{slug}_s{i}_raw.mp4"
            norm = RUN / f"{slug}_s{i}_norm.mp4"
            if norm.exists() and norm.stat().st_size > 100_000:
                continue
            if not raw.exists():
                fetch_clip(q, pexels_key, raw)
            normalize_clip(raw, norm, dur=5)

        # 4) Build props for Remotion (5 clips × 5s; end card scene is rendered by the comp itself)
        clips_rel = [str((RUN / f"{slug}_s{i}_norm.mp4").relative_to(OUTPUT)) for i in range(1, 6)]
        audio_rel = str(vo.relative_to(OUTPUT))
        captions = words_evenly_timed(v["captions"], audio_dur(vo))
        props = {"clips": clips_rel, "audioSrc": audio_rel,
                 "captions": captions, "endCard": v["endcard"]}
        props_file = RUN / f"{slug}_props.json"
        props_file.write_text(json.dumps(props))

        # 5) Render
        out = RUN / f"{slug}_master.mp4"
        render_remotion(props_file, out)

if __name__ == "__main__":
    asyncio.run(main())
