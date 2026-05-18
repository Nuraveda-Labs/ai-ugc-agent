#!/usr/bin/env python3
"""V7: bilingual (English + Hinglish) renders for two angles, 30s each, full
talking-head via fal OmniHuman with hand-authored captions (no Whisper).

  - 4 outputs: 01_en, 01_hi, 03_en, 03_hi
  - Voices: Adam (EN) + Rahul S (HI)  — both ElevenLabs multilingual_v2
  - Model: fal-ai/bytedance/omnihuman (image+audio talking head)
  - Captions: hand-authored from the script, even-timed across audio duration
"""
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, urllib.request

import fal_client, httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/bilingual-v7"
ACTOR = ROOT / "assets/actors/founder_unsplash_9x16.jpg"

VOICES = {
    "en": ("pNInz6obpgDQGcFmaJgB", "Adam"),
    "hi": ("2cdvnKJ5TZi631y5PN1s", "Rahul S"),
}
ELEVEN_MODEL = "eleven_multilingual_v2"

# Each script: full VO text + the caption chunks (small phrases for ASS overlay).
SCRIPTS = {
    "01_en": {
        "lang": "en",
        "vo": (
            "Cancelled five-eighty a month of SaaS this morning. "
            "Zapier, Make, n8n, Relevance, Lindy. I was renting six wrappers around the same LLM call. "
            "Bought the AI Marketing Stack Founder Stack instead. Four ninety-nine, once. Same six agents, on my GitHub, my brand. "
            "Twenty-four months of those subs would've been thirteen K. Lifetime updates. Every new agent free. "
            "If your stack feels heavy, look up example dot com. Code PROMO20 if you go for it."
        ),
        "captions": [
            "Cancelled $580/mo of SaaS",
            "this morning.",
            "Zapier, Make, n8n,",
            "Relevance, Lindy —",
            "all wrappers around",
            "the same LLM call.",
            "Bought AI Marketing Stack instead.",
            "$499. Once.",
            "Same six agents,",
            "on my GitHub. My brand.",
            "24 months of subs",
            "would've been $13K.",
            "Lifetime updates.",
            "Every new agent — free.",
            "If your stack feels heavy",
            "→ grow.example.com",
            "Code PROMO20.",
        ],
    },
    "01_hi": {
        "lang": "hi",
        "vo": (
            "Aaj subah pachaas hazaar rupay monthly ki SaaS cancel kar di. "
            "Zapier, Make, n8n, Relevance, Lindy — sab same LLM call ke wrappers thay. "
            "AI Marketing Stack Founder Stack le liya. Nau hazaar nau sau ninety-nine, ek baar. Wahi six agents, par ab apne GitHub par, apne brand ke saath. "
            "Do saal ka subscription bach gaya. Plus lifetime updates. Har naya agent free. "
            "Stack heavy lagta hai? example dot com slash in. Code PROMO20."
        ),
        "captions": [
            "Aaj ₹50,000/month ki",
            "SaaS cancel kar di.",
            "Zapier, Make, n8n,",
            "Relevance, Lindy —",
            "sab same LLM call ke",
            "wrappers thay.",
            "AI Marketing Stack Founder Stack",
            "le liya. ₹9,999. Ek baar.",
            "Wahi six agents,",
            "par ab apne GitHub par.",
            "Do saal ka subscription",
            "bach gaya.",
            "Lifetime updates.",
            "Har naya agent — free.",
            "Stack heavy lagta hai?",
            "→ grow.example.com/in",
            "Code PROMO20.",
        ],
    },
    "03_en": {
        "lang": "en",
        "vo": (
            "Five clients. One agent. Seventy-five hundred a month. "
            "Most freelancers chase one-offs and start the cycle every first of the month. "
            "I deploy the Ads Operator agent for one client at fifteen hundred a month. Five of those is seventy-five hundred MRR. "
            "Setup is one weekend. Two clients pays the bundle back. Every client after is pure margin. "
            "If recurring revenue is the goal, look up example dot com. Code PROMO20."
        ),
        "captions": [
            "5 clients. 1 agent.",
            "$7,500 a month.",
            "Most freelancers chase",
            "one-off projects.",
            "Cycle restarts every",
            "first of the month.",
            "I deploy Ads Operator",
            "at $1,500/mo per client.",
            "5 × $1,500 = $7,500 MRR.",
            "Setup: one weekend.",
            "Two clients pays",
            "the bundle back.",
            "Every client after",
            "is pure margin.",
            "If recurring revenue",
            "is the goal →",
            "grow.example.com",
            "Code PROMO20.",
        ],
    },
    "03_hi": {
        "lang": "hi",
        "vo": (
            "Paanch clients. Ek agent. Ek lakh pachhattar hazaar a month. "
            "Most freelancers project chase karte hain. Har pehli tareekh ko cycle restart hota hai. "
            "Main Ads Operator agent ek client ke liye pachatis hazaar month deploy karta hu. Paanch clients matlab ek lakh pachhattar hazaar MRR. "
            "Setup ek weekend. Do clients ka revenue se bundle paid back. Aage sab pure margin. "
            "Recurring revenue chahiye? example dot com slash in. Code PROMO20."
        ),
        "captions": [
            "5 clients. 1 agent.",
            "₹1.75 lakh a month.",
            "Freelancers project chase",
            "karte hain.",
            "Har pehli tareekh",
            "cycle restart hota hai.",
            "Main Ads Operator",
            "₹35,000/month pe deploy",
            "karta hu — per client.",
            "5 × ₹35K = ₹1.75L MRR.",
            "Setup: ek weekend.",
            "Do clients pays back",
            "the bundle.",
            "Aage sab pure margin.",
            "Recurring revenue chahiye?",
            "→ grow.example.com/in",
            "Code PROMO20.",
        ],
    },
}

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: hero,Inter,82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def fmt_t(t: float) -> str:
    cs = int(round(t * 100))
    h = cs // 360000; cs %= 360000
    m = cs // 6000; cs %= 6000
    s = cs // 100; cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

async def tts(voice_id: str, text: str, out: pathlib.Path) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = {
        "text": text, "model_id": ELEVEN_MODEL,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True},
    }
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(url, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept":"audio/mpeg"}, json=body)
        r.raise_for_status(); out.write_bytes(r.content)
    print(f"[tts] {out.name} {out.stat().st_size//1024}KB")

def audio_dur(p: pathlib.Path) -> float:
    s = subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode().strip()
    return float(s)

def write_ass(captions: list[str], total_s: float, out: pathlib.Path) -> None:
    n = len(captions)
    chunk = total_s / n
    lines = [ASS_HEADER]
    for i, txt in enumerate(captions):
        st = i * chunk
        en = (i + 1) * chunk - 0.05
        safe = txt.replace(",", ",").replace("→", "→")
        lines.append(f"Dialogue: 0,{fmt_t(st)},{fmt_t(en)},hero,,0,0,0,,{safe}")
    out.write_text("\n".join(lines))
    print(f"[ass] {out.name} {n} cues over {total_s:.1f}s")

def omnihuman(audio: pathlib.Path, out: pathlib.Path) -> None:
    img_url = fal_client.upload_file(str(ACTOR))
    aud_url = fal_client.upload_file(str(audio))
    print(f"[omni] {out.name} submit")
    result = fal_client.subscribe(
        "fal-ai/bytedance/omnihuman/v1.5",
        arguments={
            "image_url": img_url, "audio_url": aud_url,
            "prompt": "Static medium close-up. A relaxed indie agency founder speaks directly into the camera, confident and matter-of-fact, with natural micro-expressions, occasional subtle blinks, and gentle hand gestures for emphasis. Authentic UGC selfie energy, warm friendly tone.",
            "resolution": "720p",
        },
        with_logs=True,
    )
    url = (result.get("video") or {}).get("url")
    if not url: raise SystemExit(f"no url: {result}")
    urllib.request.urlretrieve(url, out)
    print(f"[omni] -> {out.name} ({out.stat().st_size//1024}KB)")

def burn(video: pathlib.Path, ass: pathlib.Path, out: pathlib.Path) -> None:
    esc = str(ass).replace("'", "\\'").replace(":", "\\:")
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-i",str(video),
        "-vf",f"ass='{esc}'",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
        "-c:a","copy","-movflags","+faststart", str(out)
    ], check=True)
    print(f"[burn] {out.name}")

async def main() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

    # 1) TTS sequential (ElevenLabs concurrency-limits free/starter plans)
    for slug, s in SCRIPTS.items():
        out = RUN / f"{slug}_vo.mp3"
        if out.exists() and out.stat().st_size > 50_000:
            print(f"[tts] skip {out.name} (cached)"); continue
        vid = VOICES[s["lang"]][0]
        await tts(vid, s["vo"], out)

    # 2) For each: OmniHuman + ASS + burn (skip cached)
    for slug, s in SCRIPTS.items():
        audio = RUN / f"{slug}_vo.mp3"
        raw = RUN / f"{slug}_raw.mp4"
        ass = RUN / f"{slug}.ass"
        final = RUN / f"{slug}_final.mp4"
        if final.exists() and final.stat().st_size > 500_000:
            print(f"[skip] {slug} cached"); continue
        if not raw.exists() or raw.stat().st_size < 100_000:
            omnihuman(audio, raw)
        write_ass(s["captions"], audio_dur(audio), ass)
        burn(raw, ass, final)
        print(f"[done] {slug} -> {final}")

if __name__ == "__main__":
    asyncio.run(main())
