# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] — 2026-05-18

### Added

- Initial open-source release of the AI UGC agent pipeline.
- Brief format (YAML): product / audience / hook_angles / cta.
- HeyGen Video Agent CLI integration (primary render path).
- Remotion + Pexels + ElevenLabs + ffmpeg fallback pipeline.
- Render iteration scripts (`scripts/render_v6.py` → `render_v18_video_agent.py`)
  documenting what worked at each stage of development.
- Caption rendering (ASS + burn-in via ffmpeg).
- BGM mixing scripts.
- Smoke tests covering caption retry, variant picker, media cleanup.

### Removed (extracted to a separate proprietary repo)

- Internal Claude Code skill (`glitch-ugc-pro`) — operational guardrails,
  cost-management rules, and brand-specific tuning live elsewhere.
- Brand-specific actor photos.
- Generated demo output (`output/`) — produced fresh by each run.
