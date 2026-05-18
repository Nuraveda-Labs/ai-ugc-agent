#!/usr/bin/env python3
"""V9: all-b-roll Meta-safe ads (no faces, no competitor names, no $ claims).

Per video (~30s):
  6 Seedance b-roll scenes × 5s
  Single ElevenLabs VO mp3 covers all 30s, muxed under concatenated visuals
  Hand-authored captions burned, evenly timed across audio

Cost: ~$2.40/video (4 videos = ~$10) vs $15/video on v8.
"""
from __future__ import annotations
import asyncio, os, pathlib, subprocess, sys, urllib.request

import fal_client, httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/broll-v9"

VOICES = {
    "en": "pNInz6obpgDQGcFmaJgB",  # Adam
    "hi": "2cdvnKJ5TZi631y5PN1s",  # Rahul S
}
ELEVEN_MODEL = "eleven_multilingual_v2"

# Meta-safe scripts: no specific earnings, no competitor names, generic enough to pass review.
VIDEOS = {
    "01_en": {
        "lang": "en",
        "vo": (
            "Cleaned up my software stack this morning. "
            "Too many tools. All thin wrappers around the same model. "
            "Bought one founder stack instead. Six production agents. One time. "
            "On my GitHub. My brand. My infrastructure. "
            "Lifetime updates included. Every new agent free, forever. "
            "If your stack feels heavy, look up example dot com."
        ),
        "scenes": [
            "Macro tracking shot of a Mac desktop showing dozens of overlapping browser tabs and software subscription dashboards, gentle zoom out revealing the chaos, soft mechanical keyboard clicks and credit-card swipe sound, premium minimal product UI, neon-red accents, cinematic shallow depth of field, vertical 9:16.",
            "Close-up of a generic SaaS billing dashboard with monthly invoice line items animating with bright red strikethrough crossing each line one by one, totals fading down to zero, soft notification chimes, premium minimal aesthetic, neon-red accents, cinematic depth of field, vertical 9:16.",
            "Macro tracking shot of a sleek dark macOS Terminal window on a high-end retina monitor, monospaced cursor typing 'npx founder-stack deploy', then six AI agent module names cascading in one after another with bright neon-green checkmarks — Ads, Sales, Social, Voice, MCP, Shopify — soft particle glow around each tick, satisfying mechanical keyboard clicks and a confirmation chime, premium developer launch aesthetic, cinematic depth of field, vertical 9:16.",
            "Macro shot of a GitHub repository file tree expanding from collapsed to fully open, then a config JSON file with brand name, primary color, and logo URL animating, soft UI motion, gentle keyboard clicks, premium dev tool aesthetic, cinematic depth, vertical 9:16.",
            "Macro tracking shot of a GitHub commit history scrolling continuously upward, version tags animating in v1.0, v1.1, v1.2, v1.3, v1.4, with soft particle glow around each new tag, gentle mechanical keyboard clicks, neon-green and white accents, premium developer aesthetic, cinematic depth, vertical 9:16.",
            "Macro tracking shot of a clean modern landing page hero on a high-end retina monitor, the URL grow.example.com animating in with subtle particle glow and a soft notification chime, premium minimal product aesthetic, cinematic shallow depth, vertical 9:16."
        ],
        "captions": [
            "Cleaned up my stack today.",
            "Too many tools.|All wrappers around the same model.",
            "One founder stack.|6 production agents.|Once.",
            "My GitHub. My brand. My infra.",
            "Lifetime updates.|Every new agent — free.",
            "→ grow.example.com",
        ],
    },
    "01_hi": {
        "lang": "hi",
        "vo": (
            "Aaj subah apni software stack clean kar di. "
            "Bahut saare tools. Sab same model ke wrappers thay. "
            "Ek founder stack le liya. Six production agents. Ek baar. "
            "Apne GitHub par. Apne brand mein. Apni infra par. "
            "Lifetime updates included. Har naya agent free, hamesha ke liye. "
            "Stack heavy lagta hai? example dot com slash in dekho."
        ),
        "scenes": [
            "Macro tracking shot of a Mac desktop showing dozens of overlapping browser tabs and software subscription dashboards, gentle zoom out revealing the chaos, soft mechanical keyboard clicks, premium minimal product UI, neon-red accents, cinematic shallow depth of field, vertical 9:16.",
            "Close-up of a generic SaaS billing dashboard with monthly invoice line items animating with bright red strikethrough crossing each line one by one, rupee totals fading down to zero, soft notification chimes, premium minimal aesthetic, neon-red accents, cinematic depth of field, vertical 9:16.",
            "Macro tracking shot of a sleek dark macOS Terminal window on a high-end retina monitor, monospaced cursor typing 'npx founder-stack deploy', then six AI agent module names cascading in one after another with bright neon-green checkmarks — Ads, Sales, Social, Voice, MCP, Shopify — soft particle glow around each tick, satisfying mechanical keyboard clicks and a confirmation chime, premium developer launch aesthetic, cinematic depth of field, vertical 9:16.",
            "Macro shot of a GitHub repository file tree expanding from collapsed to fully open, then a config JSON file with brand name, primary color, and logo URL animating, soft UI motion, gentle keyboard clicks, premium dev tool aesthetic, cinematic depth, vertical 9:16.",
            "Macro tracking shot of a GitHub commit history scrolling continuously upward, version tags animating in v1.0, v1.1, v1.2, v1.3, v1.4, with soft particle glow around each new tag, gentle mechanical keyboard clicks, neon-green and white accents, premium developer aesthetic, cinematic depth, vertical 9:16.",
            "Macro tracking shot of a clean modern landing page hero on a high-end retina monitor, the URL grow.example.com slash in animating in with subtle particle glow and a soft notification chime, premium minimal product aesthetic, cinematic shallow depth, vertical 9:16."
        ],
        "captions": [
            "Aaj apni stack clean kar di.",
            "Bahut tools.|Sab same model ke wrappers.",
            "Ek founder stack.|6 production agents.|Ek baar.",
            "Mera GitHub. Mera brand.",
            "Lifetime updates.|Har naya agent — free.",
            "→ grow.example.com/in",
        ],
    },
    "03_en": {
        "lang": "en",
        "vo": (
            "Five clients. One agent. Recurring. "
            "Most freelancers chase one-off projects. The cycle restarts every month. "
            "I deploy the ads agent for clients. Same code, every brand. "
            "Setup is one weekend per client. "
            "Each client pays monthly. Margin grows with every signup. "
            "If recurring revenue is the goal, look up example dot com."
        ),
        "scenes": [
            "Macro tracking shot of a calendar app showing five recurring monthly client meeting blocks animating in across the same day each month, soft notification chimes, gentle UI motion, premium minimal aesthetic, neon-blue accents, cinematic shallow depth of field, vertical 9:16.",
            "Macro tracking shot of a project dashboard showing one-off project cards stacking and collapsing repeatedly, then a recurring revenue chart line ascending steadily upward replacing them, gentle UI motion, soft mechanical keyboard clicks, premium minimal aesthetic, neon-green and white accents, cinematic depth, vertical 9:16.",
            "Macro tracking shot of a sleek ads management dashboard with active campaigns auto-optimizing in real time, ROAS climbing, CPA dropping, soft chart animations, premium dashboard aesthetic, neon-blue and green accents, cinematic depth of field, vertical 9:16.",
            "Macro shot of a brand config JSON file with a brand name and primary color animating between several different brands, then five separate dashboard windows tiling on screen each with a different brand logo, premium dev tool aesthetic, gentle UI motion, vertical 9:16.",
            "Macro tracking shot of a recurring billing dashboard with monthly invoice cards animating in one after another, MRR counter climbing steadily upward, soft chime, premium dashboard aesthetic, neon-green accents, cinematic shallow depth, vertical 9:16.",
            "Macro tracking shot of a clean modern landing page hero on a high-end retina monitor, the URL grow.example.com animating in with subtle particle glow and a soft notification chime, premium minimal product aesthetic, cinematic shallow depth, vertical 9:16."
        ],
        "captions": [
            "5 clients. 1 agent. Recurring.",
            "One-off projects = cycle restarts.",
            "Same agent. Every brand.",
            "Setup: one weekend per client.",
            "Margin grows with every signup.",
            "→ grow.example.com",
        ],
    },
    "03_hi": {
        "lang": "hi",
        "vo": (
            "Paanch clients. Ek agent. Recurring. "
            "Most freelancers one-off projects chase karte hain. Har mahine cycle restart hota hai. "
            "Main ads agent clients ke liye deploy karta hu. Same code, har brand. "
            "Setup ek weekend, per client. "
            "Har client monthly pay karta hai. Margin badhta jata hai. "
            "Recurring revenue chahiye? example dot com slash in."
        ),
        "scenes": [
            "Macro tracking shot of a calendar app showing five recurring monthly client meeting blocks animating in across the same day each month, soft notification chimes, gentle UI motion, premium minimal aesthetic, neon-blue accents, cinematic shallow depth of field, vertical 9:16.",
            "Macro tracking shot of a project dashboard showing one-off project cards stacking and collapsing repeatedly, then a recurring revenue chart line ascending steadily upward replacing them, gentle UI motion, soft mechanical keyboard clicks, premium minimal aesthetic, neon-green and white accents, cinematic depth, vertical 9:16.",
            "Macro tracking shot of a sleek ads management dashboard with active campaigns auto-optimizing in real time, ROAS climbing, CPA dropping, soft chart animations, premium dashboard aesthetic, neon-blue and green accents, cinematic depth of field, vertical 9:16.",
            "Macro shot of a brand config JSON file with a brand name and primary color animating between several different brands, then five separate dashboard windows tiling on screen each with a different brand logo, premium dev tool aesthetic, gentle UI motion, vertical 9:16.",
            "Macro tracking shot of a recurring billing dashboard with monthly invoice cards animating in one after another, MRR counter climbing steadily upward, soft chime, premium dashboard aesthetic, neon-green accents, cinematic shallow depth, vertical 9:16.",
            "Macro tracking shot of a clean modern landing page hero on a high-end retina monitor, the URL grow.example.com slash in animating in with subtle particle glow and a soft notification chime, premium minimal product aesthetic, cinematic shallow depth, vertical 9:16."
        ],
        "captions": [
            "5 clients. 1 agent. Recurring.",
            "One-off projects = cycle restart.",
            "Same agent. Har brand.",
            "Setup: ek weekend per client.",
            "Margin badhta jata hai.",
            "→ grow.example.com/in",
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
Style: hero,Inter,90,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

def fmt_t(t):
    cs = int(round(t * 100)); h = cs // 360000; cs %= 360000; m = cs // 6000; cs %= 6000; s = cs // 100; cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

async def tts(voice_id, text, out):
    body = {"text": text, "model_id": ELEVEN_MODEL,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}}
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                         headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept":"audio/mpeg"}, json=body)
        r.raise_for_status(); out.write_bytes(r.content)
    print(f"[tts] {out.name} {out.stat().st_size//1024}KB")

def audio_dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode().strip())

def seedance(prompt, out, dur=5):
    print(f"[seedance] {out.name} submit")
    r = fal_client.subscribe("fal-ai/bytedance/seedance/v1/pro/text-to-video",
        arguments={"prompt": prompt, "aspect_ratio":"9:16", "duration": str(dur), "resolution":"1080p"},
        with_logs=False)
    url = (r.get("video") or {}).get("url")
    if not url: raise SystemExit(f"no url: {r}")
    urllib.request.urlretrieve(url, out); print(f"[seedance] -> {out.name} ({out.stat().st_size//1024}KB)")

def normalize_silent(src, dst):
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(src),
                    "-vf","scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
                    "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(dst)], check=True)

def write_ass(captions, total_s, out):
    """captions: list of strings, '|' separates lines within a chunk. Even time slice across the audio."""
    n = len(captions)
    chunk = total_s / n
    lines = [ASS_HEADER]
    for i, txt in enumerate(captions):
        st = i * chunk; en = (i + 1) * chunk - 0.05
        rendered = txt.replace("|", r"\N")
        lines.append(f"Dialogue: 0,{fmt_t(st)},{fmt_t(en)},hero,,0,0,0,,{rendered}")
    out.write_text("\n".join(lines))

def burn(video, ass, out):
    esc = str(ass).replace("'","\\'").replace(":","\\:")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(video),"-vf",f"ass='{esc}'",
                    "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
                    "-c:a","copy","-movflags","+faststart",str(out)], check=True)

async def main():
    RUN.mkdir(parents=True, exist_ok=True)
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

    # 1) TTS for each video (cached if exists)
    for vid_slug, v in VIDEOS.items():
        vo = RUN / f"{vid_slug}_vo.mp3"
        if vo.exists() and vo.stat().st_size > 5_000:
            print(f"[tts] skip {vo.name}"); continue
        await tts(VOICES[v["lang"]], v["vo"], vo)

    # 2) Seedance per scene per video (sequential, cached)
    for vid_slug, v in VIDEOS.items():
        for i, prompt in enumerate(v["scenes"], 1):
            raw = RUN / f"{vid_slug}_s{i}_silent.mp4"
            if raw.exists() and raw.stat().st_size > 100_000:
                print(f"[skip] {raw.name}"); continue
            seedance(prompt, raw, dur=5)

    # 3) For each video: normalize silent scenes, concat, mux audio, burn captions
    for vid_slug, v in VIDEOS.items():
        scene_norms = []
        for i in range(1, len(v["scenes"]) + 1):
            silent = RUN / f"{vid_slug}_s{i}_silent.mp4"
            norm = RUN / f"{vid_slug}_s{i}_norm.mp4"
            normalize_silent(silent, norm)
            scene_norms.append(norm)

        # concat silent
        list_file = RUN / f"{vid_slug}_concat.txt"
        list_file.write_text("\n".join(f"file '{p}'" for p in scene_norms))
        silent_master = RUN / f"{vid_slug}_silent_master.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(list_file),
                        "-c","copy", str(silent_master)], check=True)

        # mux VO under silent master
        vo = RUN / f"{vid_slug}_vo.mp3"
        with_audio = RUN / f"{vid_slug}_with_audio.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(silent_master),"-i",str(vo),
                        "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k",
                        "-shortest","-movflags","+faststart",str(with_audio)], check=True)

        # captions over total audio duration
        ass = RUN / f"{vid_slug}.ass"
        write_ass(v["captions"], audio_dur(vo), ass)
        master = RUN / f"{vid_slug}_master.mp4"
        burn(with_audio, ass, master)
        print(f"[master] {master}")

if __name__ == "__main__":
    asyncio.run(main())
