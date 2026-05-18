# AI UGC Agent

Open-source short-form vertical (9:16) AI UGC (user-generated-content style)
video ad pipeline for paid acquisition.

Built for **cost-per-acquisition**, not for organic views. Takes a structured
brief (`product`, `audience`, `hook_angles`) and produces a finished MP4 with
a synthesized actor, voiced script, b-roll, BGM, and TikTok-style captions.

## What it does

1. **Brief** — you write a short YAML describing the product, audience pain,
   and the hook angles you want to A/B test.
2. **Scripts** — the agent expands each hook into a full 15-30s ad body
   that shares a single CTA.
3. **Render** — pluggable rendering pipeline:
   - HeyGen Video Agent CLI (recommended primary path)
   - Pexels + Remotion + ElevenLabs + ffmpeg (manual fallback)
   - fal.ai / Higgsfield / Omnihuman (experimental variants in `scripts/`)
4. **Output** — vertical 9:16 MP4 with captions ready for Meta / TikTok ads.

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

## Install

```
uv pip install -e .          # or: pip install -e .
pnpm install                 # only if you want to use the Remotion fallback
cp .env.example .env         # then fill in HeyGen / Pexels / ElevenLabs / etc. keys
```

## Quickstart

```
cp src/ugc/briefs/example.yaml briefs/my_product.yaml
# Edit briefs/my_product.yaml with your product, audience, hook angles
ugc render briefs/my_product.yaml
```

## Why open source

This repo started as one of six agents in a closed digital-marketing
stack. The engine is general-purpose; the brand-specific prompt tuning,
operational guardrails, and proprietary fine-tuning that turn it into a
deployable product live elsewhere. What's open here is **the pipeline** —
brief format, render adapters, caption tooling, BGM mixing, the v6-→-v18
iteration history showing what worked and what didn't.

## License

MIT — see `LICENSE`.
