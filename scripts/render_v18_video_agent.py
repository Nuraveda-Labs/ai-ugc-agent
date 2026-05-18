#!/usr/bin/env python3
"""V18: HeyGen Video Agent — fully-managed UGC ad render via API only.

Per video:
  POST /v3/video-agents with the script as `prompt`
  Poll session until video_id appears
  Poll video_status until completed
  Download mp4

No fal, no Pexels, no ElevenLabs, no ffmpeg. HeyGen handles narrator,
b-roll, BGM, captions internally.

Cost: ~$2/min of generated video.

Usage:
  python3 scripts/render_v18_video_agent.py [angle_slug ...]
  # default: runs only the first angle in VIDEOS for a cheap quality check
  # pass 'all' to run every angle
"""
from __future__ import annotations
import json, os, pathlib, sys, time

import httpx

ROOT = pathlib.Path(".")
RUN = ROOT / "output/ai-ugc-agent-pro/heygen-agent-v18"
HEYGEN_BASE = os.environ.get("HEYGEN_API_BASE", "https://api.heygen.com")

# Each prompt is what we hand the Video Agent. Mirrors the v14 brief format —
# the Agent uses everything (hook/problem/solution/proof/cta + style cues).
VIDEOS = {
    "v20_marketer_hi": {
        "prompt": (
            "30-second vertical 9:16 UGC ad. Hinglish (Hindi+English mix). Indian MALE agency owner POV.\n\n"
            "CHARACTER: 32-year-old Indian MAN. Indie agency owner. Runs Meta ads for 4 D2C clients. "
            "Lives in Bangalore. Casual t-shirt or polo, light beard, short dark hair. "
            "Talks like he's telling a friend over chai — half-smile, slight quiet pride, no theatrics. "
            "MALE — NOT female. NOT a woman. Use HE/HIM throughout.\n\n"
            "SETTING: His home office. Late afternoon golden light through a window. One laptop on a small desk. "
            "A plant. His phone face-down. Real, lived-in, NOT a studio.\n\n"
            "ENERGY: Quiet flex. Like he figured something out last month and is still slightly surprised it works. "
            "Talks fast on the setup, slows down on the punchlines.\n\n"
            "NARRATOR: Young Indian MALE voice. Conversational Hinglish. Casual founder energy. "
            "MUST be male — NOT female. NOT a Bollywood announcer. NOT corporate.\n\n"
            "SHOT-BY-SHOT:\n\n"
            "[0–3s] THREE QUICK BEATS, each ~0.7s, cuts hard between them. "
            "Beat 1 = CLOSE-UP on his face, looks at camera, half-smile. "
            "Beat 2 = INSERT shot of a Notion checklist with an AI agent card highlighted. "
            "Beat 3 = BACK to his face, slight nod:\n"
            "LINE: \"Marketer hu. Coder nahi. Mera AI agent live hai.\"\n"
            "ON-SCREEN TEXT (3 beats matching the cuts): \"Marketer.\" → \"Not a coder.\" → \"Agent live.\"\n\n"
            "[3–10s] CUT to his laptop screen — a Claude/ChatGPT chat thread, then a half-finished dashboard, "
            "then his hand pushing the laptop slightly away in frustration:\n"
            "LINE: \"Pehle mahino tak Claude pe banata raha. Demo to bana leta tha, launch hi nahi ho pata tha. "
            "Har project 'ab production kaise karein' pe mar jata tha.\"\n"
            "ON-SCREEN: \"Demo bana. Launch nahi.\"\n\n"
            "[10–18s] CUT to a clean Notion page with 6 AI agent cards, then his hand clicking 'Connect Account' "
            "inside Meta Ads Manager, then a green 'Deployed' toast:\n"
            "LINE: \"Ek kit le liya — chhe ready-to-launch AI agents. Ads wala chuna. "
            "Client ka account connect kiya. Deploy. Bas.\"\n"
            "ON-SCREEN: \"6 agents. One kit. Done.\"\n\n"
            "[18–25s] CUT to Meta Ads dashboard with a chart climbing overnight, then his phone buzzing Monday morning, "
            "then a Razorpay subscription-renewal notification:\n"
            "LINE: \"Mere sone ke baad bhi chalta hai. Monday subah report inbox mein. "
            "Client har mahine renew karta hai.\"\n"
            "ON-SCREEN: \"Sleep mode. Active client.\"\n\n"
            "[25–30s] BACK to his face, calm:\n"
            "LINE: \"Marketer ho aur AI samajh nahi aata? grow.example.com slash in. Code PROMO20.\"\n"
            "END CARD: \"grow.example.com/in\" / tagline \"AI service jo clients monthly pay karte hain. "
            "Code likhna nahi aata? Koi baat nahi.\" / small \"Code PROMO20 = 20% off\"\n\n"
            "MUSIC: Low-key chill lo-fi instrumental. Ducked under VO via sidechain. "
            "Slight upward swell on the end card reveal.\n\n"
            "CAPTIONS: Burned-in, Roman-script Hinglish, TikTok-style word-by-word reveals. "
            "White text, neon-green accent on these keywords: \"marketer\", \"deploy\", \"Monday subah\", \"renew\". "
            "Bottom-third positioned. Safe-area aware.\n\n"
            "DO NOT use: female narrator, female character, female on-screen presenter, "
            "white seamless studio backgrounds, American/British narrators, GitHub repos, terminal windows, "
            "code editors, IDE screenshots, multi-tenant database diagrams, anything that looks like 'developer's monitor.'\n\n"
            "DO use: Indian male agency owner on-screen, real Indian home office, warm afternoon natural light, "
            "Meta Ads Manager screens, Notion checklists, Razorpay/Stripe billing, Slack notifications, "
            "casual phone-buzzing moments, founder-at-desk b-roll."
        ),
    },
    "v20_marketer_en": {
        "prompt": (
            "30-second vertical 9:16 UGC ad. English. Marketer/agency-owner POV — NOT a developer.\n\n"
            "CHARACTER: 30-year-old MAN. Indie agency owner. Runs Meta ads for 5 D2C/SaaS clients. "
            "Lives in a walkable city — Brooklyn, Lisbon, or Mexico City. Casual t-shirt, light stubble. "
            "Talks like he's telling a friend at a coffee shop — half-smile, quiet pride, no theatrics. "
            "MALE — NOT female. NOT a woman. Use HE/HIM throughout.\n\n"
            "SETTING: His home office. Late afternoon golden light through a window. One laptop on a small desk. "
            "A plant. His phone face-down. Real, lived-in, NOT a studio.\n\n"
            "ENERGY: Quiet flex. He figured something out a month ago and is still slightly surprised it works. "
            "Talks fast on the setup, slows on the punchlines.\n\n"
            "NARRATOR: Young MALE voice. Conversational, casual, mid-pitch. "
            "MUST be male — NOT female. NOT corporate-American polish. NOT British presenter.\n\n"
            "SHOT-BY-SHOT:\n\n"
            "[0–3s] CLOSE-UP on his face. Half-smile. Direct to camera:\n"
            "LINE: \"I'm a marketer, not a developer. My clients pay me to run AI for them now.\"\n"
            "ON-SCREEN TEXT: \"Marketer. Not a developer.\"\n\n"
            "[3–10s] CUT to his laptop screen — a Claude chat thread, then a half-finished dashboard, "
            "then his sigh + push laptop slightly away:\n"
            "LINE: \"I tried building with Claude for months. I'd make a working demo. I just couldn't launch it. "
            "Every project died at 'okay now make it real.'\"\n"
            "ON-SCREEN: \"Demo built. Never launched.\"\n\n"
            "[10–18s] CUT to a clean Notion page with 6 AI agent cards, then his hand clicking 'Connect Account' "
            "in Meta Ads Manager, then a green 'Deployed' toast:\n"
            "LINE: \"Bought a kit with six ready-to-launch AI agents. Picked the one that runs ads. "
            "Connected my client's account. Hit deploy. Done.\"\n"
            "ON-SCREEN: \"6 agents. One kit. Done.\"\n\n"
            "[18–25s] CUT to Meta Ads dashboard with a chart climbing overnight, then his phone buzzing Monday morning, "
            "then a Stripe subscription-renewal notification:\n"
            "LINE: \"It runs while I sleep. Reports land Monday morning. My client renews every month. "
            "I check in for an hour.\"\n"
            "ON-SCREEN: \"Sleep mode. Active client.\"\n\n"
            "[25–30s] BACK to his face, calm:\n"
            "LINE: \"If you're a marketer trying to figure out the AI thing, look at "
            "grow.example.com. Code PROMO20.\"\n"
            "END CARD: \"grow.example.com\" / tagline \"AI services your clients pay for monthly. "
            "No coding required.\" / small \"Code PROMO20 = 20% off\"\n\n"
            "MUSIC: Low-key chill lo-fi instrumental. Ducked under VO via sidechain. "
            "Slight upward swell on the end card.\n\n"
            "CAPTIONS: Burned-in, TikTok-style word-by-word reveals. "
            "White text, neon-green accent on keywords: \"marketer\", \"deploy\", \"Monday morning\", \"renews\". "
            "Bottom-third positioned, safe-area aware.\n\n"
            "DO NOT use: female narrator, female character, female on-screen presenter, "
            "white seamless studio backgrounds, GitHub repos, terminal windows, code editors, IDE screenshots, "
            "database diagrams, anything that looks like 'developer's monitor.'\n\n"
            "DO use: male agency owner on-screen, real home office, warm natural light, Meta Ads Manager screens, "
            "Notion checklists, Stripe billing, Slack notifications, casual phone-buzzing moments, "
            "founder-at-desk b-roll."
        ),
    },
    "a6_not_engineer_hi": {
        "prompt": (
            "Create a 30-second vertical 9:16 UGC ad for an Indian audience.\n"
            "Use a Hindi-speaking, conversational, young Indian male narrator (NOT corporate, NOT American).\n"
            "Tone: casual founder talking to peers in Hinglish (Hindi words written in English script).\n"
            "Captions: burned-in, English/Roman script (Hinglish), TikTok-style word-by-word reveals.\n"
            "Visual style: real-looking laptop screens, code editors, dashboards, GitHub, modern Indian home office b-roll. NO white seamless backgrounds. NO American-looking actors.\n"
            "Background music: low-key chill lo-fi instrumental, ducked under VO.\n\n"
            "Script:\n"
            "HOOK (0–3s): Main engineer nahi hu. Maine multi-tenant AI agent ship kar diya — paying client ke liye.\n"
            "PROBLEM (3–10s): Claude ke saath vibe-code seekha tha. But har production attempt mein auth aur multi-tenant pe phas jata tha.\n"
            "SOLUTION (10–18s): Founder Stack production parts handle karta hai — auth, multi-tenant, billing, deploy. Main sirf brand parts edit karta hu.\n"
            "PROOF (18–25s): Client samajh raha hai main engineer hu. Maine sirf ek config file rename ki thi. Saath mein deploy ho gaya.\n"
            "CTA (25–30s): Vibe-code kar lete ho but ship nahi kar paate? grow.example.com slash in dekho. Code PROMO20 = 20% off.\n"
        ),
    },
    "a7_voice_cod_hi": {
        "prompt": (
            "Create a 30-second vertical 9:16 UGC ad for an Indian audience.\n"
            "Use a Hindi-speaking, conversational, young Indian male narrator.\n"
            "Tone: Indian D2C founder explaining a tech win to peers in Hinglish.\n"
            "Captions: burned-in, English/Roman script (Hinglish), TikTok-style word-by-word reveals.\n"
            "Visual style: Indian D2C / Shopify dashboards, voice waveforms, customer-service phone calls, courier/delivery footage, modern Indian small-business office. NO white seamless backgrounds.\n"
            "Background music: low-key chill lo-fi instrumental, ducked under VO.\n\n"
            "Script:\n"
            "HOOK (0–3s): Mere D2C client ke COD calls ab AI handle karta hai — Hindi mein, teen rupay per call.\n"
            "PROBLEM (3–10s): Sab imported voice tools corporate English bolte hain. Tier-2, Tier-3 customers ko samajh hi nahi aata.\n"
            "SOLUTION (10–18s): Founder Stack mein voice agent hai — LiveKit aur Sarvam. Hindi, Punjabi, Tamil, dus Indian languages.\n"
            "PROOF (18–25s): Real call duration ek minute. Cost teen rupay. Ek mid-volume merchant ka teen din mein bundle paid back.\n"
            "CTA (25–30s): Indian D2C ke liye banaya hai — grow.example.com slash in. Code PROMO20 = 20% off.\n"
        ),
    },
    "v21_x1_insider_en": {
        "prompt": (
            "30-second vertical 9:16 UGC ad. English. Marketer/agency-owner POV — NOT a developer.\n\n"
            "CHARACTER: 30-year-old MAN. Indie agency owner. Runs Meta ads for 5 D2C/SaaS clients. "
            "Lives in a walkable city — Brooklyn, Lisbon, or Mexico City. Casual t-shirt, light stubble. "
            "Talks like he just figured out a hack and wants to tell his agency friend over coffee. "
            "MALE — NOT female. Use HE/HIM throughout.\n\n"
            "SETTING: His home office. Late afternoon golden light through a window. One laptop, plant, "
            "phone face-down. Real, lived-in, NOT a studio.\n\n"
            "ENERGY: Smart-insider feel. Like he's letting the viewer in on a secret. "
            "Slight forward lean on the hook. Eye contact direct.\n\n"
            "NARRATOR: Young MALE voice. Conversational, casual, mid-pitch, slight 'I just figured this out' energy. "
            "MUST be male. NOT corporate-American polish. NOT British presenter.\n\n"
            "SHOT-BY-SHOT:\n\n"
            "[0–3s] CLOSE-UP on his face. Slight forward lean. Direct to camera:\n"
            "LINE: \"Here's what nobody tells you about selling AI services.\"\n\n"
            "[3–10s] CUT to a Notion CRM with 3 client cards labeled 'Renewed', then a Slack DM thread "
            "with 'less work, more sleep' kind of energy, then a calendar with empty afternoons:\n"
            "LINE: \"Clients don't want AI. They want to stop hiring. They want fewer Slack messages. "
            "They want their Monday emails to be shorter.\"\n\n"
            "[10–18s] CUT to a clean Notion page with 6 AI agent cards visible, then his hand connecting "
            "a client account in Meta Ads Manager, then a green 'Active' status pill:\n"
            "LINE: \"I sell that. AI agents that just run — ads, sales, social. Six of them in one repo. "
            "One config per client. They never see 'AI' in my pitch.\"\n\n"
            "[18–25s] CUT to a Stripe MRR dashboard with three new recurring subscriptions added, then "
            "his phone showing 'Client: signed' text-message threads:\n"
            "LINE: \"I closed three retainers in two weeks. Each one told me they were tired of "
            "'more headcount, more meetings.' I sold them silence.\"\n\n"
            "[25–30s] BACK to his face, calm direct delivery:\n"
            "LINE: \"If you're trying to sell AI and getting blank stares, look at "
            "grow.example.com. Code PROMO20.\"\n"
            "END CARD: \"grow.example.com\" / tagline \"Sell silence. Not software.\" / "
            "small \"Code PROMO20 = 20% off\"\n\n"
            "MUSIC: Low-key chill lo-fi instrumental. Ducked under VO via sidechain. "
            "Slight upward swell on the end card.\n\n"
            "CAPTIONS: ONE unified track only — TikTok-style word-by-word reveals of the spoken VO. "
            "White text, neon-green accent on key nouns/numbers (e.g. \"AI services\", \"three retainers\", "
            "\"silence\", \"PROMO20\"). Bottom-third positioned, safe-area aware. "
            "DO NOT add separate beat-styled overlay text on top — the word-by-word track IS the only on-screen text.\n\n"
            "DO NOT use: female narrator, female character, female on-screen presenter, "
            "white seamless studio backgrounds, GitHub repos, terminal windows, code editors, IDE screenshots, "
            "database diagrams, anything that looks like 'developer's monitor.', "
            "double caption tracks (no auto-caption on top of beat text).\n\n"
            "DO use: male agency owner on-screen, real home office, warm natural light, Notion CRM, "
            "Meta Ads Manager, Stripe MRR dashboard, Slack DMs, calendar with empty afternoons, "
            "phone notifications. Casual lived-in agency-owner vibe."
        ),
    },
    "v21_x3_new_seo_en": {
        "prompt": (
            "30-second vertical 9:16 UGC ad. English. Marketer/agency-owner POV — NOT a developer.\n\n"
            "CHARACTER: 30-year-old MAN. Indie agency owner with 8 years in SEO/Meta ads. Has seen waves before. "
            "Casual hoodie or t-shirt, light stubble. Talks like he's pulling the viewer aside at a coffee shop "
            "to give them advice before the wave hits. MALE — NOT female. Use HE/HIM throughout.\n\n"
            "SETTING: His home office. Late afternoon golden light. One laptop, plant, phone face-down. "
            "Real, lived-in, NOT a studio.\n\n"
            "ENERGY: Early-mover energy. Slight urgency under the calm. Like he's seen this movie before and "
            "wants to give the viewer the heads-up.\n\n"
            "NARRATOR: Young MALE voice. Conversational, slight urgency under casual, mid-pitch. "
            "MUST be male. NOT corporate-American polish. NOT British presenter.\n\n"
            "SHOT-BY-SHOT:\n\n"
            "[0–3s] CLOSE-UP on his face. Direct to camera. Slight raised eyebrow:\n"
            "LINE: \"AI is the new SEO. And right now, you're the SEO guy in 2008.\"\n\n"
            "[3–10s] CUT to an archival-looking screenshot of 2008 Google search results, then a 2026 "
            "agency landing page with 'AI services' as a hero offer, then a chart of search interest in 'AI marketing' climbing:\n"
            "LINE: \"The window is open. In two years, 'AI marketing' will be table stakes. "
            "Today it's a margin you can charge for.\"\n\n"
            "[10–18s] CUT to a clean Notion with 6 AI agent cards, then a pitch deck slide reading "
            "'+ AI Services Retainer', then his hand drag-and-dropping it into a client proposal:\n"
            "LINE: \"I bought a kit with six production AI agents. I added 'AI services' to my pitch deck. "
            "Same client list. Higher retainers.\"\n\n"
            "[18–25s] CUT to a Stripe MRR dashboard with 3 'Upgraded' notifications, then text messages "
            "with clients saying 'when can it start?':\n"
            "LINE: \"Three of my clients upgraded last month. None asked 'what model is it.' "
            "They asked 'when can it start.'\"\n\n"
            "[25–30s] BACK to his face, calm direct:\n"
            "LINE: \"If you want to be early on this, look at grow.example.com. Code PROMO20.\"\n"
            "END CARD: \"grow.example.com\" / tagline \"Be the AI guy in 2026, not the SEO guy in 2014.\" / "
            "small \"Code PROMO20 = 20% off\"\n\n"
            "MUSIC: Low-key chill lo-fi instrumental. Slightly more momentum than typical (subtle pulse). "
            "Ducked under VO via sidechain. Upward swell on the end card.\n\n"
            "CAPTIONS: ONE unified track only — TikTok-style word-by-word reveals of the spoken VO. "
            "White text, neon-green accent on key nouns/numbers (e.g. \"AI is the new SEO\", \"2008\", "
            "\"two years\", \"three of my clients\", \"PROMO20\"). Bottom-third positioned. "
            "DO NOT add separate beat-styled overlay text on top — the word-by-word track IS the only on-screen text.\n\n"
            "DO NOT use: female narrator, female character, female on-screen presenter, "
            "white seamless studio backgrounds, GitHub repos, terminal windows, code editors, IDE screenshots, "
            "double caption tracks.\n\n"
            "DO use: male agency owner on-screen, real home office, warm natural light, archival 2008 web "
            "look for one b-roll cut, modern agency pitch deck, Notion, Stripe MRR, Meta Ads Manager, "
            "phone text-message threads."
        ),
    },
    "v22_career_change_en_female": {
        "prompt": (
            "30-second vertical 9:16 UGC ad. English. Female agency-owner POV.\n\n"
            "CHARACTER: 28-year-old WOMAN. Just left a full-time corporate marketing job last quarter. "
            "Now runs her own one-person agency from cafes and her apartment. Casual sweater or tee, "
            "minimal jewelry, hair tied back. Talks like she's catching up with a college friend over "
            "coffee — confident but still slightly surprised it worked. "
            "FEMALE — NOT male. NOT a man. Use SHE/HER throughout.\n\n"
            "SETTING: Sunlit corner of a coworking cafe — exposed brick or warm wood, plants, her laptop "
            "open with a Notion CRM, an oat-milk latte half-finished, her phone face-down. Real, lived-in, "
            "NOT a studio. Mid-morning warm window light.\n\n"
            "ENERGY: Quiet confidence + 'I can't believe this is working' surprise. Slight forward lean on "
            "the hook. Smile lines around the eyes. Talks fast on the setup beats, slows down on the punchlines.\n\n"
            "NARRATOR: Young FEMALE voice. Conversational, warm, mid-pitch, slightly higher than corporate. "
            "Hint of 'just-figured-this-out' excitement under the calm. MUST be female. NOT corporate "
            "presenter, NOT NPR voice, NOT British. American-leaning casual.\n\n"
            "SHOT-BY-SHOT:\n\n"
            "[0–3s] CLOSE-UP on her face at the cafe table. Slight forward lean, direct to camera, "
            "small smile:\n"
            "LINE: \"I left my full-time job last quarter. First month solo, I signed four retainers.\"\n\n"
            "[3–10s] CUT to her laptop screen showing a 'two weeks notice' email draft sent, then a "
            "Notion page titled 'Solo agency plan' with empty checkboxes, then a calendar with a "
            "single anxious meeting block:\n"
            "LINE: \"I thought I'd need a team. Or a co-founder. Or six months of runway. "
            "I had three months of savings and a pitch deck I wasn't sure about.\"\n\n"
            "[10–18s] CUT to a Notion page with 6 AI agent cards visible, then her dragging a card "
            "labeled 'Meta Ads Agent' into a client folder, then a green 'Active' status pill appearing:\n"
            "LINE: \"Then I bought a kit. Six production AI agents in one folder. I picked the ads one. "
            "Connected my first client's account. Pitched them a managed service. They said yes.\"\n\n"
            "[18–25s] CUT to a Stripe MRR dashboard with four recurring subscriptions added in 30 days, "
            "then her phone showing 'Client #4: signed' text-message celebrations:\n"
            "LINE: \"Four retainers in thirty days. Zero employees. I work from this cafe most mornings. "
            "I haven't opened my old work Slack in weeks.\"\n\n"
            "[25–30s] BACK to her face at the cafe, calm direct delivery, slight smile:\n"
            "LINE: \"If you're sitting on a job you want to leave, look at grow.example.com. "
            "Code PROMO20.\"\n"
            "END CARD: \"grow.example.com\" / tagline \"Six AI agents. One folder. Your agency, "
            "your hours.\" / small \"Code PROMO20 = 20% off\"\n\n"
            "MUSIC: Low-key chill lo-fi instrumental with a slightly warm, optimistic feel (NOT moody). "
            "Ducked under VO via sidechain. Upward swell on the end card.\n\n"
            "CAPTIONS: ONE unified track only — TikTok-style word-by-word reveals of the spoken VO. "
            "White text, soft-coral or warm-pink accent on emotion words (\"left\", \"yes\", \"four retainers\", "
            "\"weeks\", \"PROMO20\"). Bottom-third positioned, safe-area aware. "
            "DO NOT add separate beat-styled overlay text on top — the word-by-word track IS the only "
            "on-screen text.\n\n"
            "DO NOT use: male narrator, male character, male on-screen presenter, "
            "white seamless studio backgrounds, GitHub repos, terminal windows, code editors, IDE screenshots, "
            "double caption tracks, anything that looks like 'developer's monitor.'\n\n"
            "DO use: female agency owner on-screen, real sunlit coworking cafe vibe, warm window light, "
            "Notion CRM, Meta Ads Manager, Stripe MRR dashboard, two-weeks-notice email mock, calendar app, "
            "phone text-message threads. Lived-in 'first month on my own' agency-owner feel."
        ),
    },
    # English fallback variants — Video Agent's strongest mode
    "a6_not_engineer_en": {
        "prompt": (
            "Create a 30-second vertical 9:16 UGC ad. Casual founder talking to peers.\n"
            "Use a young, casual, conversational male narrator (NOT corporate-American, NOT British).\n"
            "Captions: burned-in, TikTok-style word-by-word reveals.\n"
            "Visuals: real laptops, code editors, GitHub repos, modern home office b-roll. Avoid white seamless studio backgrounds.\n"
            "Background music: low-key lo-fi instrumental, ducked under VO.\n\n"
            "Script:\n"
            "HOOK (0–3s): I'm not an engineer. I just shipped a multi-tenant AI agent for a paying client.\n"
            "PROBLEM (3–10s): I learned to vibe-code with Claude. But every production attempt died at auth and multi-tenant.\n"
            "SOLUTION (10–18s): AI Marketing Stack Founder Stack handles the production parts — auth, multi-tenant, billing. I edit one config file.\n"
            "PROOF (18–25s): My client thinks I'm an engineer. I just renamed a config and deployed.\n"
            "CTA (25–30s): If you can vibe-code but can't ship, look at grow.example.com. Code PROMO20 = 20% off.\n"
        ),
    },
}

def hg(method, path, **kw):
    url = f"{HEYGEN_BASE}{path}"
    r = httpx.request(method, url, headers={"X-Api-Key": os.environ["HEYGEN_API_KEY"]}, timeout=60, **kw)
    if r.status_code >= 300:
        raise SystemExit(f"HeyGen {method} {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()

def create_session(prompt: str) -> str:
    # mode=generate → one-shot fire-and-forget. mode=chat would pause
    # for confirmation after blueprint, which we don't want for batch render.
    r = hg("POST", "/v3/video-agents", json={"prompt": prompt, "mode": "generate"})
    sid = (r.get("data") or r).get("session_id")
    if not sid: raise SystemExit(f"no session_id: {r}")
    return sid

def session_status(sid: str) -> dict:
    r = hg("GET", f"/v3/video-agents/{sid}")
    return r.get("data") or r

def send_message(sid: str, content: str) -> None:
    hg("POST", f"/v3/video-agents/{sid}/messages", json={"content": content})

def confirm_blueprint(sid: str, *, max_wait_s: int = 180) -> None:
    """Wait until the agent has emitted a blueprint resource (status moves
    out of initial planning), then send a 'go ahead' confirmation. HeyGen
    Video Agent now pauses for user approval after the blueprint."""
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        sess = session_status(sid)
        msgs = sess.get("messages", []) or []
        # blueprint emitted = there's a model 'resource' message
        has_blueprint = any(m.get("role") == "model" and m.get("type") == "resource" for m in msgs)
        if has_blueprint:
            send_message(sid, "Looks great. Go ahead and build it.")
            print(f"  [confirm] blueprint approved", flush=True)
            return
        time.sleep(5)
    # blueprint never showed up — just try sending anyway
    send_message(sid, "Go ahead and build it.")
    print(f"  [confirm] no blueprint seen, sent go-ahead anyway", flush=True)

def video_status(vid: str) -> dict:
    r = hg("GET", f"/v1/video_status.get?video_id={vid}")
    return r.get("data") or r

def wait_for_video(sid: str, deadline_s: int = 1800) -> str:
    """Poll until session has video_id, then download URL."""
    t0 = time.time()
    last_msg = ""
    while time.time() - t0 < deadline_s:
        sess = session_status(sid)
        st = (sess.get("status") or "").lower()
        vid = sess.get("video_id")
        # show last model message if it changed
        msgs = [m for m in sess.get("messages", []) if m.get("role") == "model"]
        if msgs:
            new_msg = (msgs[-1].get("content") or "")[:120]
            if new_msg != last_msg:
                print(f"  [agent] {new_msg}", flush=True)
                last_msg = new_msg
        if vid:
            vs = video_status(vid)
            v_st = (vs.get("status") or "").lower()
            print(f"  [video {vid}] {v_st}", flush=True)
            if v_st in ("completed", "succeeded"):
                return vs.get("video_url") or vs.get("url")
            if v_st in ("failed", "errored"):
                raise SystemExit(f"video failed: {vs}")
        if st in ("failed", "errored", "stopped"):
            raise SystemExit(f"session failed: {sess}")
        time.sleep(15)
    raise SystemExit("timeout waiting for video")

def main():
    RUN.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if "all" in args:
        slugs = list(VIDEOS.keys())
    elif args:
        slugs = args
    else:
        slugs = [next(iter(VIDEOS))]   # default: first only (cheap quality check)

    for slug in slugs:
        if slug not in VIDEOS:
            print(f"skip unknown: {slug}", file=sys.stderr); continue
        out_mp4 = RUN / f"{slug}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 100_000:
            print(f"[skip] {slug} cached"); continue
        print(f"\n=== {slug} ===")
        try:
            sid = create_session(VIDEOS[slug]["prompt"])
            print(f"  session_id={sid}  (track at https://app.heygen.com/video-agents/{sid})")
            # mode=generate auto-proceeds past blueprint — no confirmation needed.
            url = wait_for_video(sid)
            print(f"  downloading {url[:80]}...")
            with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
                r.raise_for_status()
                with open(out_mp4, "wb") as f:
                    for chunk in r.iter_bytes(64*1024): f.write(chunk)
            print(f"  -> {out_mp4} ({out_mp4.stat().st_size//1024} KB)")
            sess = session_status(sid)
            (RUN / f"{slug}_session.json").write_text(json.dumps(sess, indent=2, default=str))
        except SystemExit as e:
            print(f"  [FAIL] {slug}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"  [FAIL] {slug}: {type(e).__name__}: {e}", file=sys.stderr)
            continue

if __name__ == "__main__":
    main()
