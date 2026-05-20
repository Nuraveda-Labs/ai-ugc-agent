# AI UGC Agent

[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)
[![Part of Mesh Pilot](https://img.shields.io/badge/Mesh%20Pilot-stack-black.svg)](https://meshpilot.app)
[![Mirrored on Codeberg](https://img.shields.io/badge/codeberg-mirror-black.svg)](https://codeberg.org/Glitch_Exec_Lab/ai-ugc-agent)

> **Part of the [Mesh Pilot](https://meshpilot.app) open-source 6-agent marketing stack.**
> Short-form vertical (9:16) AI UGC video ad pipeline — built for cost-per-acquisition, not organic views.

Takes a structured brief (`product`, `audience`, `hook_angles`) and produces a finished MP4 with a synthesized actor, voiced script, b-roll, BGM, and TikTok-style captions. Designed to plug into the ads agent's approval flow — every variant queues for human review before it spends a dollar.

## Quick start

```bash
git clone https://gitlab.com/mesh-pilot/ai-ugc-agent.git
# or: git clone https://codeberg.org/Glitch_Exec_Lab/ai-ugc-agent.git
cd ai-ugc-agent

uv pip install -e .          # or: pip install -e .
pnpm install                 # only if you want the Remotion fallback path
cp .env.example .env         # HeyGen / Pexels / ElevenLabs / etc. keys

cp src/ugc/briefs/example.yaml briefs/my_product.yaml
# edit briefs/my_product.yaml with your product, audience, hook angles
ugc render briefs/my_product.yaml
```

## What it does

1. **Brief** — you write a short YAML describing the product, audience pain, and the hook angles you want to A/B test.
2. **Scripts** — the agent expands each hook into a full 15–30s ad body around a single CTA.
3. **Render** — pluggable rendering pipeline:
   - HeyGen Video Agent CLI (recommended primary path)
   - Pexels + Remotion + ElevenLabs + ffmpeg (manual fallback)
   - fal.ai / Higgsfield / Omnihuman (experimental variants in `scripts/`)
4. **Output** — vertical 9:16 MP4 with captions ready for Meta / TikTok ads.

## The HITL pattern (shared across the stack)

Generated variants don't auto-publish. They're produced as draft assets that the [ads agent](https://gitlab.com/mesh-pilot/ai-ads-agent) (or any downstream uploader) queues through its approval gate. In the [Mesh Pilot](https://meshpilot.app) cockpit, those drafts show up in the same web inbox where every cross-agent proposal lands.

## Why open source

This repo started as one of six agents in a closed digital-marketing stack. The engine is general-purpose; brand-specific prompt tuning, operational guardrails, and proprietary fine-tuning that turn it into a deployable product live elsewhere. What's open here is **the pipeline** — brief format, render adapters, caption tooling, BGM mixing, plus the v6→v18 iteration history showing what worked and what didn't.

## Layout

```
src/ugc/        # core Python package — pipeline + brief loader
scripts/        # render iterations (v6 → v18) showing the path
                # from naive ffmpeg to HeyGen Video Agent
remotion/       # Remotion-based caption + b-roll composer (the fallback)
tests/          # smoke tests + caption / variant unit tests
assets/bgm/     # background music clips (only royalty-free clips ship)
pyproject.toml  # Python deps (uv / pip install -e .)
package.json    # Remotion / Node deps (pnpm install)
```

## Companions in the stack

| Agent | Domain | Repo |
|---|---|---|
| AI Ads Agent | Meta / Google / TikTok / Amazon Ads | [mesh-pilot/ai-ads-agent](https://gitlab.com/mesh-pilot/ai-ads-agent) |
| AI Sales Agent | Outbound B2B sales | [mesh-pilot/ai-sales-agent](https://gitlab.com/mesh-pilot/ai-sales-agent) |
| AI Social Agent | Multi-platform posting + ORM | [mesh-pilot/ai-social-agent](https://gitlab.com/mesh-pilot/ai-social-agent) |
| **AI UGC Agent** | This repo | — |
| AI Voice Agent | LiveKit-based phone agent | [mesh-pilot/ai-voice-agent](https://gitlab.com/mesh-pilot/ai-voice-agent) |
| AI SEO Agent | Shopify SEO autopilot | [mesh-pilot/ai-seo-agent](https://gitlab.com/mesh-pilot/ai-seo-agent) |

In production they're orchestrated by **[Mesh Pilot](https://meshpilot.app)** — the closed-source cockpit that runs all six in concert with shared brand context, a single web approval inbox, and cross-agent handoffs.

## Mirrors

- GitLab: [`mesh-pilot/ai-ugc-agent`](https://gitlab.com/mesh-pilot/ai-ugc-agent)
- Codeberg: [`Glitch_Exec_Lab/ai-ugc-agent`](https://codeberg.org/Glitch_Exec_Lab/ai-ugc-agent)

## Contributing

Bug reports + PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution shape (issue-first for non-trivial changes, preserve the HITL gate, conventional commits).

## Security

Security reports go to `support@meshpilot.app` — see [SECURITY.md](SECURITY.md). Please do not open public issues for vulnerabilities.

## Code of conduct

Be kind, stay on scope — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) — fork it, ship products with it, no attribution required.

---

Built by [Mesh Pilot](https://meshpilot.app).
