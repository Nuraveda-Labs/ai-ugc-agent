#!/usr/bin/env python3
"""V8: 4-scene UGC ads with b-roll cuts + ethnically-matched actors per language.

Per video (~30s):
  Scene 1 — TALKING HEAD (hook, 3-4s) — OmniHuman 720p
  Scene 2 — B-ROLL (problem visual, 5s) — Seedance 9:16 1080p
  Scene 3 — B-ROLL (solution visual, 5s) — Seedance 9:16 1080p
  Scene 4 — TALKING HEAD (proof+cta, 12-15s) — OmniHuman 720p

Audio: 4 TTS chunks per video. Talking-head scenes consume their chunk via
OmniHuman; b-roll scenes get the chunk muxed under silent video.
Captions: hand-authored, evenly timed across each scene's audio.
"""
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, urllib.request

import fal_client, httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/scenes-v8"

VOICES = {
    "en": ("pNInz6obpgDQGcFmaJgB", "Adam"),
    "hi": ("2cdvnKJ5TZi631y5PN1s", "Rahul S"),
}
ELEVEN_MODEL = "eleven_multilingual_v2"

ACTORS = {
    "en": ROOT / "assets/actors/founder_unsplash_9x16.jpg",
    "hi": ROOT / "assets/actors/founder_indian_9x16.jpg",
}

# 4 scenes per video. talkinghead | broll. text → audio chunk; prompt → b-roll visual.
VIDEOS = {
    "01_en": {"lang": "en", "scenes": [
        {"i": 1, "kind": "talkinghead", "vo": "Cancelled five-eighty a month of SaaS this morning."},
        {"i": 2, "kind": "broll", "duration": 5, "vo": "Zapier, Make, n8n, Relevance, Lindy. Six wrappers around the same LLM call.",
         "prompt": "Macro tracking shot of a laptop screen showing a stack of overlapping browser tabs and Stripe invoice receipts for SaaS subscriptions like Zapier, Make, n8n, with bright red strikethrough animation crossing each line one by one and totals fading down, soft mechanical keyboard clicks and credit-card swipe sound, premium minimal product UI, neon-red and white accents, cinematic shallow depth of field, vertical 9:16."},
        {"i": 3, "kind": "broll", "duration": 5, "vo": "Bought the AI Marketing Stack Founder Stack. Four ninety-nine, once. Six agents, my GitHub, my brand.",
         "prompt": "Macro tracking shot of a sleek dark macOS Terminal window on a high-end retina monitor, monospaced cursor typing 'git clone ai-marketing-stack' then 'npx ai-marketing-stack deploy', six AI agent names cascading in one after another with bright neon-green checkmarks — Ads Operator, Sales Agent, Social Media, Voice AI, MCP Builder, Shopify Boilerplate — soft particle glow around each tick, satisfying mechanical keyboard clicks and a confirmation chime, premium developer launch aesthetic, cinematic depth of field, vertical 9:16."},
        {"i": 4, "kind": "talkinghead", "vo": "Twenty-four months of those subs would've been thirteen K. Lifetime updates. Every new agent free. If your stack feels heavy, look up example dot com. Code PROMO20 if you go for it."},
    ], "captions": [
        ("Cancelled $580/mo SaaS today.", 0, None),  # whole-scene
        ("Zapier, Make, n8n, Relevance, Lindy.", None, None),
        ("Bought AI Marketing Stack. $499. Once.", None, None),
        ("24 months: saved $13K. Lifetime updates.|grow.example.com|Code PROMO20.", None, None),
    ]},
    "01_hi": {"lang": "hi", "scenes": [
        {"i": 1, "kind": "talkinghead", "vo": "Aaj subah pachaas hazaar rupay monthly ki SaaS cancel kar di."},
        {"i": 2, "kind": "broll", "duration": 5, "vo": "Zapier, Make, n8n, Relevance, Lindy. Same LLM call ke wrappers thay.",
         "prompt": "Macro tracking shot of a laptop screen showing a stack of overlapping browser tabs and invoice receipts for SaaS subscriptions like Zapier, Make, n8n, with bright red strikethrough animation crossing each line one by one and rupee totals fading down, soft mechanical keyboard clicks, premium minimal product UI, neon-red and white accents, cinematic shallow depth of field, vertical 9:16."},
        {"i": 3, "kind": "broll", "duration": 5, "vo": "AI Marketing Stack Founder Stack le liya. Nau hazaar nau sau ninety-nine. Ek baar.",
         "prompt": "Macro tracking shot of a sleek dark macOS Terminal window on a high-end retina monitor, monospaced cursor typing 'git clone ai-marketing-stack' then 'npx ai-marketing-stack deploy', six AI agent names cascading in one after another with bright neon-green checkmarks — Ads Operator, Sales Agent, Social Media, Voice AI, MCP Builder, Shopify Boilerplate — soft particle glow around each tick, satisfying mechanical keyboard clicks and a confirmation chime, premium developer launch aesthetic, cinematic depth of field, vertical 9:16."},
        {"i": 4, "kind": "talkinghead", "vo": "Wahi six agents, par ab apne GitHub par, apne brand ke saath. Do saal ka subscription bach gaya. Plus lifetime updates. Har naya agent free. Stack heavy lagta hai? example dot com slash in. Code PROMO20."},
    ], "captions": [
        ("Aaj ₹50,000/mo SaaS cancel.", None, None),
        ("Zapier, Make, n8n, Lindy.", None, None),
        ("AI Marketing Stack ₹9,999. Ek baar.", None, None),
        ("2 saal ka subscription bach gaya.|grow.example.com/in|Code PROMO20.", None, None),
    ]},
    "03_en": {"lang": "en", "scenes": [
        {"i": 1, "kind": "talkinghead", "vo": "Five clients. One agent. Seventy-five hundred a month."},
        {"i": 2, "kind": "broll", "duration": 5, "vo": "Most freelancers chase one-offs. Cycle restarts every first of the month.",
         "prompt": "Macro tracking shot of a calendar app showing recurring monthly client meetings on the first of each month, then panning to a Stripe MRR dashboard with a green ascending revenue chart climbing past seven thousand five hundred dollars MRR, gentle UI motion, soft notification chime, premium minimal aesthetic, neon-green and white accents, cinematic shallow depth of field, vertical 9:16."},
        {"i": 3, "kind": "broll", "duration": 5, "vo": "I deploy the Ads Operator agent at fifteen hundred a month per client.",
         "prompt": "Macro tracking shot of a Meta Ads dashboard automatically optimizing campaigns, with metrics tickers updating in real time, ROAS climbing, CPA dropping, then a spreadsheet overlay showing the math five times one thousand five hundred equals seven thousand five hundred MRR with each line animating in, soft mechanical keyboard clicks, premium dashboard aesthetic, neon-blue and green accents, cinematic depth, vertical 9:16."},
        {"i": 4, "kind": "talkinghead", "vo": "Five of those is seventy-five hundred MRR. Setup is one weekend. Two clients pays the bundle back. Every client after is pure margin. If recurring revenue is the goal, look up example dot com. Code PROMO20."},
    ], "captions": [
        ("5 clients. 1 agent. $7,500/mo.", None, None),
        ("Most freelancers chase one-offs.", None, None),
        ("Ads Operator: $1,500/mo per client.", None, None),
        ("5 × $1,500 = $7,500 MRR.|2 clients pay back the bundle.|grow.example.com|Code PROMO20.", None, None),
    ]},
    "03_hi": {"lang": "hi", "scenes": [
        {"i": 1, "kind": "talkinghead", "vo": "Paanch clients. Ek agent. Ek lakh pachhattar hazaar a month."},
        {"i": 2, "kind": "broll", "duration": 5, "vo": "Most freelancers project chase karte hain. Har pehli tareekh cycle restart hota hai.",
         "prompt": "Macro tracking shot of a calendar app showing recurring monthly client meetings on the first of each month, then panning to a Stripe MRR dashboard with a green ascending revenue chart climbing, gentle UI motion, soft notification chime, premium minimal aesthetic, neon-green and white accents, cinematic shallow depth of field, vertical 9:16."},
        {"i": 3, "kind": "broll", "duration": 5, "vo": "Ads Operator agent ek client ke liye pachatis hazaar month deploy karta hu.",
         "prompt": "Macro tracking shot of a Meta Ads dashboard auto-optimizing campaigns with metrics tickers updating in real time, ROAS climbing, CPA dropping, then a spreadsheet overlay showing the math five times thirty-five thousand equals one lakh seventy-five thousand rupees MRR with lines animating in, soft mechanical keyboard clicks, premium dashboard aesthetic, neon-blue and green accents, cinematic depth, vertical 9:16."},
        {"i": 4, "kind": "talkinghead", "vo": "Paanch clients matlab ek lakh pachhattar hazaar MRR. Setup ek weekend. Do clients ka revenue se bundle paid back. Aage sab pure margin. Recurring revenue chahiye? example dot com slash in. Code PROMO20."},
    ], "captions": [
        ("5 clients. 1 agent. ₹1.75L/mo.", None, None),
        ("Project chase cycle har mahine.", None, None),
        ("Ads Operator: ₹35K/mo per client.", None, None),
        ("5 × ₹35K = ₹1.75L MRR.|Do clients pay back bundle.|grow.example.com/in|Code PROMO20.", None, None),
    ]},
}

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: hero,Inter,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def fmt_t(t):
    cs = int(round(t * 100)); h = cs // 360000; cs %= 360000; m = cs // 6000; cs %= 6000; s = cs // 100; cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

async def tts(voice_id, text, out):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = {"text": text, "model_id": ELEVEN_MODEL,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}}
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(url, headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept":"audio/mpeg"}, json=body)
        r.raise_for_status(); out.write_bytes(r.content)
    print(f"[tts] {out.name} {out.stat().st_size//1024}KB")

def audio_dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode().strip())

def write_ass(text, dur, out):
    """text uses '|' to split lines; each line gets equal time slice."""
    lines_in = [l.strip() for l in text.split("|") if l.strip()]
    n = len(lines_in)
    chunk = dur / n
    out_lines = [ASS_HEADER]
    for i, t in enumerate(lines_in):
        out_lines.append(f"Dialogue: 0,{fmt_t(i*chunk)},{fmt_t((i+1)*chunk-0.05)},hero,,0,0,0,,{t}")
    out.write_text("\n".join(out_lines))

def omnihuman(actor, audio, out):
    img_url = fal_client.upload_file(str(actor)); aud_url = fal_client.upload_file(str(audio))
    print(f"[omni] {out.name} submit")
    r = fal_client.subscribe("fal-ai/bytedance/omnihuman/v1.5",
        arguments={"image_url": img_url, "audio_url": aud_url,
                   "prompt": "Static medium close-up. A relaxed indie founder speaks directly into the camera, confident and matter-of-fact, with natural micro-expressions, occasional subtle blinks, gentle hand gestures for emphasis on key numbers. Authentic UGC selfie energy.",
                   "resolution": "720p"},
        with_logs=False)
    url = (r.get("video") or {}).get("url")
    if not url: raise SystemExit(f"omnihuman no url: {r}")
    urllib.request.urlretrieve(url, out); print(f"[omni] -> {out.name} ({out.stat().st_size//1024}KB)")

def seedance(prompt, dur, out):
    print(f"[seedance] {out.name} submit")
    r = fal_client.subscribe("fal-ai/bytedance/seedance/v1/pro/text-to-video",
        arguments={"prompt": prompt, "aspect_ratio":"9:16", "duration": str(int(dur)), "resolution":"1080p"},
        with_logs=False)
    url = (r.get("video") or {}).get("url")
    if not url: raise SystemExit(f"seedance no url: {r}")
    urllib.request.urlretrieve(url, out); print(f"[seedance] -> {out.name} ({out.stat().st_size//1024}KB)")

def mux(video, audio, out):
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),
                    "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k",
                    "-shortest","-movflags","+faststart",str(out)], check=True)

def burn(video, ass, out):
    esc = str(ass).replace("'","\\'").replace(":","\\:")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(video),"-vf",f"ass='{esc}'",
                    "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
                    "-c:a","copy","-movflags","+faststart",str(out)], check=True)

def normalize(src, dst):
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(src),
                    "-vf","scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                    "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
                    "-c:a","aac","-b:a","128k","-ar","48000","-ac","2",
                    "-af","aresample=async=1:first_pts=0,apad","-shortest",str(dst)], check=True)

async def main():
    RUN.mkdir(parents=True, exist_ok=True)
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

    # 1) TTS per scene per video (sequential to avoid 409s)
    for vid_slug, v in VIDEOS.items():
        voice_id = VOICES[v["lang"]][0]
        for sc in v["scenes"]:
            out = RUN / f"{vid_slug}_s{sc['i']}_vo.mp3"
            if out.exists() and out.stat().st_size > 5_000:
                print(f"[tts] skip {out.name}"); continue
            await tts(voice_id, sc["vo"], out)

    # 2) Render scenes
    for vid_slug, v in VIDEOS.items():
        actor = ACTORS[v["lang"]]
        for sc in v["scenes"]:
            i = sc["i"]
            audio = RUN / f"{vid_slug}_s{i}_vo.mp3"
            raw = RUN / f"{vid_slug}_s{i}_raw.mp4"
            if raw.exists() and raw.stat().st_size > 100_000:
                print(f"[skip] {raw.name}"); continue
            if sc["kind"] == "talkinghead":
                omnihuman(actor, audio, raw)
            else:
                tmp = RUN / f"{vid_slug}_s{i}_silent.mp4"
                seedance(sc["prompt"], sc["duration"], tmp)
                mux(tmp, audio, raw); tmp.unlink()
            print(f"[scene] {vid_slug} s{i} done")

    # 3) Captions, burn, normalize, concat per video
    for vid_slug, v in VIDEOS.items():
        scene_finals = []
        for idx, sc in enumerate(v["scenes"]):
            i = sc["i"]
            raw = RUN / f"{vid_slug}_s{i}_raw.mp4"
            ass = RUN / f"{vid_slug}_s{i}.ass"
            burned = RUN / f"{vid_slug}_s{i}_final.mp4"
            cap_text = v["captions"][idx][0]
            write_ass(cap_text, audio_dur(RUN / f"{vid_slug}_s{i}_vo.mp3"), ass)
            burn(raw, ass, burned)
            # normalize for concat
            norm = RUN / f"{vid_slug}_s{i}_norm.mp4"
            normalize(burned, norm)
            scene_finals.append(norm)
        # concat
        list_file = RUN / f"{vid_slug}_concat.txt"
        list_file.write_text("\n".join(f"file '{p}'" for p in scene_finals))
        master = RUN / f"{vid_slug}_master.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(list_file),
                        "-c","copy","-movflags","+faststart",str(master)], check=True)
        print(f"[master] {master}")

if __name__ == "__main__":
    asyncio.run(main())
