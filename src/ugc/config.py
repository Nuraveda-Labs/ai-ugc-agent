"""Settings — pydantic-settings, reads from .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- HeyGen — talking-head avatars + voice clone + video translate ---
    heygen_api_key: str = ""
    heygen_default_avatar_id: str = ""   # stock avatar URN — set per brief in CLI
    heygen_default_voice_id: str = ""    # default voice when not using avatar's bundled voice
    heygen_api_base: str = "https://api.heygen.com"

    # --- LLM script writer ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openai_smart_model: str = "gpt-4o"
    openai_cheap_model: str = "gpt-4o-mini"

    # --- Image / video gen for b-roll ---
    fal_api_key: str = ""

    # --- ElevenLabs — fallback TTS when HeyGen avatar's bundled voice is wrong ---
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_model: str = "eleven_turbo_v2_5"

    # --- Ad platforms (Phase 2) ---
    meta_ads_access_token: str = ""
    meta_ads_account_id: str = ""
    tiktok_ads_access_token: str = ""
    tiktok_ads_account_id: str = ""

    # --- captions.ai / Mirage — HeyGen competitor (talking-head AI actor) ---
    # API: https://captions.ai/help/api-reference  Base: https://api.mirage.app
    captions_api_key: str = ""                 # auth (header: x-api-key)
    mirage_api_base: str = "https://api.mirage.app"
    mirage_default_voice_id: str = ""          # discover via `glitch-ugc mirage-probe`
    mirage_actor_image: str = ""               # path to JPEG/PNG used as lipsync source

    # --- HyperFrames — HTML→MP4 composition layer (github.com/heygen-com/hyperframes) ---
    hyperframes_npx_bin: str = "npx"        # override if npx isn't on $PATH
    hyperframes_workdir: str = ".hyperframes"  # one-time `npx hyperframes init .` happens here

    # --- Storage ---
    output_dir: str = "output"

    # --- Runtime ---
    dispatch_mode: str = "live"   # live | dry_run

    @property
    def is_dry_run(self) -> bool:
        return self.dispatch_mode == "dry_run"


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
