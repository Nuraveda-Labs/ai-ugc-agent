#!/usr/bin/env python3
"""V10: real-footage UGC ads using Pexels Videos API + ElevenLabs VO.

Per video (~30s):
  5 Pexels stock clips × 5s — real laptops, dashboards, code, calendars
  1 ffmpeg-generated URL end card × 5s
  ElevenLabs VO muxed under all 6 scenes
  Hand-authored captions burned over the audio timeline

No AI-generated visuals. No talking heads. Designed to pass Meta review.
"""
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, urllib.request

import httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/pexels-v10"

VOICES = {"en":"pNInz6obpgDQGcFmaJgB", "hi":"2cdvnKJ5TZi631y5PN1s"}
ELEVEN_MODEL = "eleven_multilingual_v2"

# Reuse v9 scripts (Meta-safe). Each scene gets a Pexels query.
VIDEOS = {
    "01_en": {"lang":"en", "vo":(
        "Cleaned up my software stack this morning. "
        "Too many tools. All thin wrappers around the same model. "
        "Bought one founder stack instead. Six production agents. One time. "
        "On my GitHub. My brand. My infrastructure. "
        "Lifetime updates included. Every new agent free, forever. "
        "If your stack feels heavy, look up example dot com."
    ), "scenes": [
        {"q":"frustrated developer laptop late night office","keywords":["laptop","developer","office","desk"]},
        {"q":"saas subscription dashboard credit card invoice","keywords":["screen","dashboard","invoice","money"]},
        {"q":"code terminal screen typing programming","keywords":["code","terminal","screen","programming"]},
        {"q":"github coding software developer screen","keywords":["github","code","screen","developer"]},
        {"q":"software update version release coding","keywords":["update","screen","code","developer"]},
    ], "captions":[
        "Cleaned up my stack today.",
        "Too many tools.|All wrappers around one model.",
        "One founder stack.|6 production agents.|Once.",
        "My GitHub. My brand. My infra.",
        "Lifetime updates.|Every new agent — free.",
        "→ grow.example.com",
    ], "endcard":{"line1":"grow.example.com","line2":"Founder Stack — buy once, own forever"}},

    "01_hi": {"lang":"hi", "vo":(
        "Aaj subah apni software stack clean kar di. "
        "Bahut saare tools. Sab same model ke wrappers thay. "
        "Ek founder stack le liya. Six production agents. Ek baar. "
        "Apne GitHub par. Apne brand mein. Apni infra par. "
        "Lifetime updates included. Har naya agent free, hamesha ke liye. "
        "Stack heavy lagta hai? example dot com slash in dekho."
    ), "scenes": [
        {"q":"indian developer laptop home office working","keywords":["laptop","developer","office","desk","indian"]},
        {"q":"subscription dashboard rupee invoice screen","keywords":["screen","dashboard","invoice","money"]},
        {"q":"code terminal screen typing programming","keywords":["code","terminal","screen","programming"]},
        {"q":"github coding software developer screen","keywords":["github","code","screen","developer"]},
        {"q":"software update version release coding","keywords":["update","screen","code","developer"]},
    ], "captions":[
        "Aaj apni stack clean kar di.",
        "Bahut tools.|Sab same model ke wrappers.",
        "Ek founder stack.|6 production agents.|Ek baar.",
        "Mera GitHub. Mera brand.",
        "Lifetime updates.|Har naya agent — free.",
        "→ grow.example.com/in",
    ], "endcard":{"line1":"grow.example.com/in","line2":"Founder Stack — ek baar khareedo, hamesha tumhara"}},

    "03_en": {"lang":"en", "vo":(
        "Five clients. One agent. Recurring. "
        "Most freelancers chase one-off projects. The cycle restarts every month. "
        "I deploy the ads agent for clients. Same code, every brand. "
        "Setup is one weekend per client. "
        "Each client pays monthly. Margin grows with every signup. "
        "If recurring revenue is the goal, look up example dot com."
    ), "scenes": [
        {"q":"calendar app meeting schedule planner laptop","keywords":["calendar","schedule","planner","screen"]},
        {"q":"freelancer working laptop coffee shop deadline","keywords":["freelancer","laptop","working","desk"]},
        {"q":"marketing dashboard analytics laptop ads","keywords":["dashboard","analytics","laptop","screen"]},
        {"q":"developer coding multi-monitor setup workspace","keywords":["developer","coding","monitor","workspace"]},
        {"q":"business growth chart revenue dashboard screen","keywords":["chart","growth","dashboard","screen","revenue"]},
    ], "captions":[
        "5 clients. 1 agent. Recurring.",
        "One-off projects = cycle restarts.",
        "Same agent. Every brand.",
        "Setup: one weekend per client.",
        "Margin grows with every signup.",
        "→ grow.example.com",
    ], "endcard":{"line1":"grow.example.com","line2":"Recurring revenue. Yours forever."}},

    "03_hi": {"lang":"hi", "vo":(
        "Paanch clients. Ek agent. Recurring. "
        "Most freelancers one-off projects chase karte hain. Har mahine cycle restart hota hai. "
        "Main ads agent clients ke liye deploy karta hu. Same code, har brand. "
        "Setup ek weekend, per client. "
        "Har client monthly pay karta hai. Margin badhta jata hai. "
        "Recurring revenue chahiye? example dot com slash in."
    ), "scenes": [
        {"q":"calendar app meeting schedule planner laptop","keywords":["calendar","schedule","planner","screen"]},
        {"q":"indian freelancer laptop home office working","keywords":["freelancer","laptop","working","indian"]},
        {"q":"marketing dashboard analytics laptop ads","keywords":["dashboard","analytics","laptop","screen"]},
        {"q":"developer coding multi-monitor setup workspace","keywords":["developer","coding","monitor","workspace"]},
        {"q":"business growth chart revenue dashboard screen","keywords":["chart","growth","dashboard","screen","revenue"]},
    ], "captions":[
        "5 clients. 1 agent. Recurring.",
        "One-off projects = cycle restart.",
        "Same agent. Har brand.",
        "Setup: ek weekend per client.",
        "Margin badhta jata hai.",
        "→ grow.example.com/in",
    ], "endcard":{"line1":"grow.example.com/in","line2":"Recurring revenue. Hamesha tumhara."}},
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

# ------- Pexels fetch -------

def pexels_search(query: str, key: str) -> list[dict]:
    url = f"https://api.pexels.com/videos/search?query={query.replace(' ', '+')}&orientation=portrait&per_page=15&size=medium"
    r = httpx.get(url, headers={"Authorization": key}, timeout=60)
    r.raise_for_status()
    return r.json().get("videos", [])

def pick_best_file(video: dict) -> dict | None:
    # Prefer portrait (height > width) HD-quality file ≥ 1080w
    portraits = [f for f in video["video_files"] if f.get("width",0) < f.get("height",0)]
    if not portraits: return None
    # rank: closest to 1080w but ≥ 1080 if available
    sized = sorted(portraits, key=lambda f: (abs(f.get("width",0)-1080), -f.get("width",0)))
    return sized[0]

def fetch_clip(query: str, key: str, out: pathlib.Path, min_dur=5) -> str:
    vids = pexels_search(query, key)
    candidates = [v for v in vids if v.get("duration",0) >= min_dur]
    if not candidates: candidates = vids
    if not candidates: raise RuntimeError(f"no Pexels clips for: {query}")
    chosen = candidates[0]; chosen_file = pick_best_file(chosen)
    if not chosen_file:
        # fallback: any file
        chosen_file = chosen["video_files"][0]
    url = chosen_file["link"]
    print(f"[pexels] {out.name} <- id={chosen['id']} dur={chosen.get('duration')}s {chosen_file.get('width')}x{chosen_file.get('height')}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120,
                      headers={"User-Agent":"Mozilla/5.0 GlitchGrowUGC/1.0"}) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_bytes(64*1024): f.write(chunk)
    return f"pexels.com/video/{chosen['id']}"

# ------- ffmpeg helpers -------

def normalize_clip(src, dst, dur=5):
    """Trim to dur, scale-and-crop to 1080×1920 30fps, no audio."""
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-i",str(src),"-t",str(dur),
        "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(dst)
    ], check=True)

def make_endcard(line1, line2, out, dur=5):
    """ffmpeg synthetic end card: dark bg + URL + tagline."""
    f1 = line1.replace(":","\\:").replace("'","\\'")
    f2 = line2.replace(":","\\:").replace("'","\\'")
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"color=c=#0a0a0a:s=1080x1920:d={dur}:r=30",
        "-vf",
        f"drawtext=text='{f1}':fontcolor=white:fontsize=72:font=Inter:x=(w-text_w)/2:y=(h-text_h)/2-40,"
        f"drawtext=text='{f2}':fontcolor=#7CFFB2:fontsize=42:font=Inter:x=(w-text_w)/2:y=(h-text_h)/2+80",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(out)
    ], check=True)

def write_ass(captions, total_s, out):
    n = len(captions); chunk = total_s / n
    lines = [ASS_HEADER]
    for i, txt in enumerate(captions):
        st = i*chunk; en = (i+1)*chunk - 0.05
        rendered = txt.replace("|", r"\N")
        lines.append(f"Dialogue: 0,{fmt_t(st)},{fmt_t(en)},hero,,0,0,0,,{rendered}")
    out.write_text("\n".join(lines))

def burn(video, ass, out):
    esc = str(ass).replace("'","\\'").replace(":","\\:")
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(video),"-vf",f"ass='{esc}'",
                    "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
                    "-c:a","copy","-movflags","+faststart",str(out)], check=True)

def audio_dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode().strip())

# ------- TTS -------

async def tts(voice_id, text, out):
    body = {"text":text, "model_id":ELEVEN_MODEL,
            "voice_settings":{"stability":0.45,"similarity_boost":0.8,"style":0.25,"use_speaker_boost":True}}
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                         headers={"xi-api-key":os.environ["ELEVENLABS_API_KEY"],"accept":"audio/mpeg"}, json=body)
        r.raise_for_status(); out.write_bytes(r.content)
    print(f"[tts] {out.name} {out.stat().st_size//1024}KB")

# ------- main -------

async def main():
    RUN.mkdir(parents=True, exist_ok=True)
    pexels_key = os.environ["PEXELS_API_KEY"]

    # 1) TTS (cached) — reuse v9 mp3s if they exist
    for vid_slug, v in VIDEOS.items():
        out = RUN / f"{vid_slug}_vo.mp3"
        if out.exists() and out.stat().st_size > 5_000:
            print(f"[tts] skip {out.name}"); continue
        # try v9 cache
        v9_cache = ROOT / f"output/ai-ugc-agent-pro/broll-v9/{vid_slug}_vo.mp3"
        if v9_cache.exists() and v9_cache.stat().st_size > 5_000:
            out.write_bytes(v9_cache.read_bytes()); print(f"[tts] reused v9 {out.name}"); continue
        await tts(VOICES[v["lang"]], v["vo"], out)

    # 2) Pexels fetch + normalize per scene
    attribution = []
    for vid_slug, v in VIDEOS.items():
        for i, sc in enumerate(v["scenes"], 1):
            raw = RUN / f"{vid_slug}_s{i}_raw.mp4"
            norm = RUN / f"{vid_slug}_s{i}_norm.mp4"
            if norm.exists() and norm.stat().st_size > 100_000:
                print(f"[skip] {norm.name}"); continue
            if not raw.exists() or raw.stat().st_size < 100_000:
                src = fetch_clip(sc["q"], pexels_key, raw)
                attribution.append(f"{vid_slug} s{i}: {src}")
            normalize_clip(raw, norm, dur=5)
        # endcard scene 6
        endcard = RUN / f"{vid_slug}_s6_norm.mp4"
        if not endcard.exists():
            make_endcard(v["endcard"]["line1"], v["endcard"]["line2"], endcard, dur=5)

    (RUN / "ATTRIBUTIONS.txt").write_text("\n".join(attribution) + "\n" if attribution else "(all cached)\n")

    # 3) Concat → mux VO → burn captions per video
    for vid_slug, v in VIDEOS.items():
        list_file = RUN / f"{vid_slug}_concat.txt"
        scene_norms = [RUN / f"{vid_slug}_s{i}_norm.mp4" for i in range(1, 7)]
        list_file.write_text("\n".join(f"file '{p}'" for p in scene_norms))
        silent_master = RUN / f"{vid_slug}_silent_master.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(list_file),
                        "-c","copy", str(silent_master)], check=True)

        vo = RUN / f"{vid_slug}_vo.mp3"
        with_audio = RUN / f"{vid_slug}_with_audio.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(silent_master),"-i",str(vo),
                        "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k",
                        "-shortest","-movflags","+faststart",str(with_audio)], check=True)

        ass = RUN / f"{vid_slug}.ass"
        write_ass(v["captions"], audio_dur(vo), ass)
        master = RUN / f"{vid_slug}_master.mp4"
        burn(with_audio, ass, master)
        print(f"[master] {master}")

if __name__ == "__main__":
    asyncio.run(main())
