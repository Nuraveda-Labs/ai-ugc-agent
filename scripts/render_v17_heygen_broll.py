#!/usr/bin/env python3
"""V17: HeyGen avatar (lipsynced to ElevenLabs VO) + Pexels b-roll + BGM.

Per video (~30s):
  Audio: existing ElevenLabs Rehan VO (cached at india-v15/*_vo.mp3)
  HeyGen: upload audio -> Aditya_public_5 lipsync clip (full ~30s)
  Visual timeline: alternate AVATAR ↔ B-ROLL every ~5s (3 avatar + 2 broll)
  BGM: synth ambient pad under VO with sidechain ducking
  Captions: kinetic Hinglish (reuse from v15 props)

  Render flow:
    1. avatar_full.mp4 (HeyGen, includes audio)
    2. broll_<i>.mp4 (Pexels, silent)
    3. extract avatar_full audio -> vo.mp3
    4. ffmpeg concat alternating silent video segments [avatar | broll | avatar | broll | avatar]
    5. mux vo.mp3 over silent timeline
    6. add BGM via add_bgm.sh
"""
from __future__ import annotations
import asyncio, json, os, pathlib, subprocess, sys, urllib.request

import httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/heygen-broll-v17"
V15 = ROOT / "output/ai-ugc-agent-pro/india-v15"
V10 = ROOT / "output/ai-ugc-agent-pro/pexels-v10"   # has Pexels India b-rolls

HEYGEN_BASE = os.environ.get("HEYGEN_API_BASE", "https://api.heygen.com")
AVATAR_ID = "Aditya_public_5"  # Indian male, casual blue shirt

# Portrait office backgrounds for HeyGen avatar (Pexels CDN URLs).
BG_OFFICE = "https://images.pexels.com/photos/19045069/pexels-photo-19045069.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1920&w=1080"
BG_DESK   = "https://images.pexels.com/photos/246121/pexels-photo-246121.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1920&w=1080"

VIDEOS = {
    "a6_not_engineer": {
        "vo_src": V15 / "a6_not_engineer_vo.mp3",
        "background_url": BG_OFFICE,
        "broll_queries": [
            "indian developer laptop home office working coding screen",
            "github code editor screen dark theme close up",
        ],
        "captions_src": V15 / "a6_not_engineer_props.json",
        "endcard_line1": "grow.example.com/in",
        "endcard_line2": "Founder Stack — engineer banne ki zaroorat nahi",
    },
    "a7_voice_cod": {
        "vo_src": V15 / "a7_voice_cod_vo.mp3",
        "background_url": BG_DESK,
        "broll_queries": [
            "indian small business owner shopify dashboard mobile phone",
            "voice waveform audio recording microphone studio",
        ],
        "captions_src": V15 / "a7_voice_cod_props.json",
        "endcard_line1": "grow.example.com/in",
        "endcard_line2": "Voice agent for Indian D2C — ₹3/call",
    },
}

# -------------------- HeyGen helpers --------------------

def heygen_upload(audio_path: pathlib.Path) -> str:
    """POST /v3/assets (multipart file) — returns asset_id."""
    print(f"[heygen] upload {audio_path.name}")
    with open(audio_path, "rb") as f:
        r = httpx.post(
            f"{HEYGEN_BASE}/v3/assets",
            headers={"X-Api-Key": os.environ["HEYGEN_API_KEY"]},
            files={"file": (audio_path.name, f.read())},
            timeout=180,
        )
    if r.status_code >= 300:
        raise SystemExit(f"heygen upload failed: {r.status_code} {r.text[:300]}")
    j = r.json()
    asset_id = (j.get("data") or {}).get("asset_id") or j.get("asset_id")
    if not asset_id:
        raise SystemExit(f"heygen upload no asset_id: {j}")
    print(f"[heygen] asset_id={asset_id}")
    return asset_id

def heygen_generate(audio_asset_id: str, out_mp4: pathlib.Path, background_url: str | None = None) -> None:
    video_input = {
        "character": {"type": "avatar", "avatar_id": AVATAR_ID, "avatar_style": "normal"},
        "voice": {"type": "audio", "audio_asset_id": audio_asset_id},
    }
    if background_url:
        video_input["background"] = {"type": "image", "url": background_url}
    body = {
        "title": f"v17 {out_mp4.stem}",
        "caption": False,
        "dimension": {"width": 720, "height": 1280},   # 9:16, lighter
        "video_inputs": [video_input],
    }
    print(f"[heygen] generate avatar (audio_asset={audio_asset_id})")
    r = httpx.post(f"{HEYGEN_BASE}/v2/video/generate",
        headers={"X-Api-Key": os.environ["HEYGEN_API_KEY"], "Content-Type": "application/json"},
        json=body, timeout=120)
    if r.status_code >= 300:
        raise SystemExit(f"heygen generate failed: {r.status_code} {r.text[:300]}")
    j = r.json()
    video_id = (j.get("data") or {}).get("video_id") or j.get("video_id")
    if not video_id:
        raise SystemExit(f"heygen no video_id: {j}")
    print(f"[heygen] video_id={video_id}, polling…")

    import time; t0 = time.time()
    while time.time() - t0 < 900:
        s = httpx.get(f"{HEYGEN_BASE}/v1/video_status.get?video_id={video_id}",
                      headers={"X-Api-Key": os.environ["HEYGEN_API_KEY"]}, timeout=30).json()
        d = s.get("data") or {}
        status = (d.get("status") or "").lower()
        if status in ("completed", "succeeded"):
            url = d.get("video_url") or d.get("url")
            urllib.request.urlretrieve(url, out_mp4)
            print(f"[heygen] done {out_mp4.name} ({out_mp4.stat().st_size//1024}KB) in {int(time.time()-t0)}s")
            return
        if status in ("failed", "errored"):
            raise SystemExit(f"heygen failed: {s}")
        time.sleep(8)
    raise SystemExit("heygen timeout")

# -------------------- Pexels helpers --------------------

def pexels_search(query, key):
    url = f"https://api.pexels.com/videos/search?query={query.replace(' ', '+')}&orientation=portrait&per_page=15&size=medium"
    r = httpx.get(url, headers={"Authorization": key}, timeout=60); r.raise_for_status()
    return r.json().get("videos", [])

def pick_best_file(video):
    portraits = [f for f in video["video_files"] if f.get("width",0) < f.get("height",0)]
    return sorted(portraits, key=lambda f: (abs(f.get("width",0)-1080), -f.get("width",0)))[0] if portraits else None

def fetch_clip(query, key, out, min_dur=5):
    vids = pexels_search(query, key)
    candidates = [v for v in vids if v.get("duration",0) >= min_dur] or vids
    v = candidates[0]; f = pick_best_file(v) or v["video_files"][0]
    print(f"[pexels] {out.name} <- id={v['id']} {f.get('width')}x{f.get('height')}")
    with httpx.stream("GET", f["link"], follow_redirects=True, timeout=120,
                      headers={"User-Agent":"Mozilla/5.0 GlitchGrowUGC/1.0"}) as r:
        r.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in r.iter_bytes(64*1024): fh.write(chunk)

# -------------------- ffmpeg helpers --------------------

def normalize_silent(src, dst, dur=None, start=0):
    """Resize to 1080×1920, 30fps, no audio. Optionally trim."""
    args = ["ffmpeg","-y","-loglevel","error","-i",str(src)]
    if dur:
        args += ["-ss", str(start), "-t", str(dur)]
    args += [
        "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(dst)
    ]
    subprocess.run(args, check=True)

def audio_dur(p):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)]).decode().strip())

# -------------------- main --------------------

def main():
    RUN.mkdir(parents=True, exist_ok=True)
    pexels_key = os.environ["PEXELS_API_KEY"]

    for slug, v in VIDEOS.items():
        avatar_full = RUN / f"{slug}_avatar_full.mp4"

        # 1) Upload VO + generate HeyGen avatar (cached)
        if not (avatar_full.exists() and avatar_full.stat().st_size > 100_000):
            asset_id = heygen_upload(v["vo_src"])
            heygen_generate(asset_id, avatar_full, background_url=v.get("background_url"))

        # full audio duration drives timeline
        dur = audio_dur(v["vo_src"])
        # 6 segments × 5s = 30s. Pattern: AVATAR / BROLL / AVATAR / BROLL / AVATAR / ENDCARD
        seg_dur = dur / 6.0

        # 2) Build avatar segments (3 cuts of 5s from the full HeyGen video)
        avatar_segs = []
        for i, start in enumerate([0, 2*seg_dur, 4*seg_dur], 1):
            seg = RUN / f"{slug}_avatar_{i}.mp4"
            if not seg.exists():
                normalize_silent(avatar_full, seg, dur=seg_dur, start=start)
            avatar_segs.append(seg)

        # 3) Build b-roll segments (2 from Pexels)
        broll_segs = []
        for i, q in enumerate(v["broll_queries"], 1):
            raw = RUN / f"{slug}_broll_{i}_raw.mp4"
            seg = RUN / f"{slug}_broll_{i}.mp4"
            if not seg.exists():
                if not raw.exists():
                    fetch_clip(q, pexels_key, raw)
                normalize_silent(raw, seg, dur=seg_dur)
            broll_segs.append(seg)

        # 4) End-card scene (synthetic, 5s)
        endcard = RUN / f"{slug}_endcard.mp4"
        if not endcard.exists():
            f1 = v["endcard_line1"].replace(":","\\:").replace("'","\\'")
            f2 = v["endcard_line2"].replace(":","\\:").replace("'","\\'")
            subprocess.run([
                "ffmpeg","-y","-loglevel","error","-f","lavfi","-i",f"color=c=#0a0a0a:s=1080x1920:d={seg_dur}:r=30",
                "-vf",
                f"drawtext=text='{f1}':fontcolor=white:fontsize=72:font=Inter:x=(w-text_w)/2:y=(h-text_h)/2-40,"
                f"drawtext=text='{f2}':fontcolor=#7CFFB2:fontsize=42:font=Inter:x=(w-text_w)/2:y=(h-text_h)/2+80",
                "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-an", str(endcard)
            ], check=True)

        # 5) Concat: AVATAR / BROLL / AVATAR / BROLL / AVATAR / ENDCARD
        timeline = [avatar_segs[0], broll_segs[0], avatar_segs[1],
                    broll_segs[1], avatar_segs[2], endcard]
        list_file = RUN / f"{slug}_concat.txt"
        list_file.write_text("\n".join(f"file '{p}'" for p in timeline))
        silent_master = RUN / f"{slug}_silent.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(list_file),
                        "-c","copy", str(silent_master)], check=True)

        # 6) Mux ElevenLabs VO under timeline (the avatar's lipsync was generated to THIS audio)
        with_audio = RUN / f"{slug}_with_audio.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(silent_master),"-i",str(v["vo_src"]),
                        "-map","0:v","-map","1:a","-c:v","copy","-c:a","aac","-b:a","192k",
                        "-movflags","+faststart", str(with_audio)], check=True)

        # 7) Burn captions (reuse v15 ASS from props if exists)
        # Easiest: regenerate from captions list inside v15 props
        props = json.loads(v["captions_src"].read_text())
        caps = props["captions"]   # [{text, startSec, endSec}, ...]
        # write ASS evenly distributed across audio dur
        ass = RUN / f"{slug}.ass"
        ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: hero,Inter,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        def fmt(t):
            cs = int(round(t*100)); h=cs//360000; cs%=360000; m=cs//6000; cs%=6000; s=cs//100; cs%=100
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
        lines = [ASS_HEADER]
        for c in caps:
            lines.append(f"Dialogue: 0,{fmt(c['startSec'])},{fmt(c['endSec'])},hero,,0,0,0,,{c['text']}")
        ass.write_text("\n".join(lines))

        master_no_bgm = RUN / f"{slug}_master_no_bgm.mp4"
        esc = str(ass).replace("'","\\'").replace(":","\\:")
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(with_audio),"-vf",f"ass='{esc}'",
                        "-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p",
                        "-c:a","copy","-movflags","+faststart", str(master_no_bgm)], check=True)

        # 8) Add BGM (synth or assets/bgm/lofi.mp3 if exists)
        bgm_file = ROOT / "assets/bgm/lofi.mp3"
        bgm_arg = str(bgm_file) if bgm_file.exists() and bgm_file.stat().st_size > 50_000 else "synth"
        master = RUN / f"{slug}_master.mp4"
        subprocess.run(["bash", str(ROOT / "scripts/add_bgm.sh"), str(master_no_bgm), bgm_arg, str(master)], check=True)
        print(f"[v17] {master}")

if __name__ == "__main__":
    main()
