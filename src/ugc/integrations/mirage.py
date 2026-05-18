"""Mirage / captions.ai REST API client.

Mirage (the API behind captions.ai) is HeyGen's main competitor for
talking-head AI avatar video. Architecturally it differs from HeyGen
in two important ways:

  1. NO avatar catalog. The caller supplies an actor reference image
     (JPEG/PNG) per render. We bundle one in `assets/actors/` and
     point the brief at it.
  2. Two-step flow: TTS first, then lipsync video render.

     POST /v1/audio/text-to-speech/{voice_id}      — text → audio bytes
     POST /v1/videos                               — multipart(image, audio) → job
     GET  /v1/videos/{id}                          — poll status
     GET  /v1/videos/{id}/content                  — download MP4

  Auth: x-api-key header.   Base: https://api.mirage.app

We expose `text_to_clip()` as the convenience equivalent of
HeyGenClient.create_short_clip() — same signature shape so the compose
pipeline can swap engines via `--engine`.
"""
from __future__ import annotations

import asyncio
import io
import pathlib
import time
from dataclasses import dataclass

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ugc.config import settings

log = structlog.get_logger(__name__)


class MirageError(RuntimeError):
    """Non-recoverable Mirage API error."""


class MirageRetryableError(MirageError):
    """Retryable error (5xx / 429 / network)."""


@dataclass
class VideoJob:
    video_id: str
    status: str           # PROCESSING | COMPLETE | FAILED | CANCELLED (lowercased)
    progress: int | None = None
    completed_at: int | None = None
    error: str | None = None


_TTS_MODEL = "mirage-audio-1"
_VIDEO_MODEL = "mirage-video-1-latest"


class MirageClient:
    """Async client. One instance per process."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        s = settings()
        self._api_key = api_key or s.captions_api_key
        if not self._api_key:
            raise MirageError("CAPTIONS_API_KEY not set")
        self._base = (api_base or s.mirage_api_base).rstrip("/")

    # ----- HTTP plumbing --------------------------------------------------

    def _headers(self, *, json_body: bool = True) -> dict[str, str]:
        h = {"x-api-key": self._api_key, "Accept": "application/json"}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, MirageRetryableError)),
    )
    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """JSON in / JSON out request."""
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.request(
                method, url, headers=self._headers(),
                params=params, json=json,
            )
        if resp.status_code in (429, 500, 502, 503, 504):
            raise MirageRetryableError(
                f"{method} {path} -> {resp.status_code} (retryable): {resp.text[:300]}"
            )
        if resp.status_code >= 400:
            raise MirageError(
                f"{method} {path} -> {resp.status_code}: {resp.text[:500]}"
            )
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    # ----- TTS ------------------------------------------------------------

    async def tts(
        self,
        *,
        text: str,
        voice_id: str,
    ) -> bytes:
        """POST /v1/audio/text-to-speech/{voice_id} — synchronous, returns audio bytes."""
        url = f"{self._base}/v1/audio/text-to-speech/{voice_id}"
        body = {"text": text, "model": _TTS_MODEL}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise MirageError(
                f"POST /v1/audio/text-to-speech/{voice_id} -> "
                f"{resp.status_code}: {resp.text[:500]}"
            )
        ct = resp.headers.get("content-type", "")
        if "audio" not in ct and "octet-stream" not in ct:
            # Some accounts return JSON-wrapped base64; surface explicitly.
            raise MirageError(
                f"TTS unexpected content-type {ct!r}: {resp.text[:300]}"
            )
        log.info(
            "mirage.tts.done",
            voice_id=voice_id, text_chars=len(text), bytes=len(resp.content),
        )
        return resp.content

    # ----- Video render --------------------------------------------------

    async def create_video(
        self,
        *,
        image_path: pathlib.Path,
        audio_bytes: bytes,
        audio_filename: str = "audio.wav",
    ) -> str:
        """POST /v1/videos (multipart: image_reference + audio_reference).

        Returns the video_id.
        """
        url = f"{self._base}/v1/videos"
        image_path = pathlib.Path(image_path)
        if not image_path.exists():
            raise MirageError(f"actor image not found: {image_path}")
        suffix = image_path.suffix.lower()
        image_mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        audio_mime = (
            "audio/wav" if audio_filename.lower().endswith(".wav") else "audio/mpeg"
        )
        files = {
            "image_reference": (
                image_path.name, image_path.read_bytes(), image_mime,
            ),
            "audio_reference": (
                audio_filename, io.BytesIO(audio_bytes), audio_mime,
            ),
            "model": (None, _VIDEO_MODEL),
        }
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                url, headers={"x-api-key": self._api_key}, files=files,
            )
        if resp.status_code in (429, 500, 502, 503, 504):
            raise MirageRetryableError(
                f"POST /v1/videos -> {resp.status_code}: {resp.text[:300]}"
            )
        if resp.status_code >= 400:
            raise MirageError(
                f"POST /v1/videos -> {resp.status_code}: {resp.text[:500]}"
            )
        data = resp.json()
        video_id = data.get("id") or data.get("video_id")
        if not video_id:
            raise MirageError(f"create_video: no id in response: {data}")
        log.info(
            "mirage.video.queued",
            video_id=video_id,
            image=str(image_path),
            audio_bytes=len(audio_bytes),
        )
        return video_id

    async def get_video(self, video_id: str) -> VideoJob:
        """GET /v1/videos/{video_id}."""
        data = await self._request_json("GET", f"/v1/videos/{video_id}")
        # Mirage uses uppercase status enums.
        status = str(data.get("status", "unknown")).lower()
        err = data.get("error")
        if isinstance(err, dict):
            err = err.get("message") or str(err)
        return VideoJob(
            video_id=video_id,
            status=status,
            progress=data.get("progress"),
            completed_at=data.get("completed_at"),
            error=err,
        )

    async def wait_for_video(
        self,
        video_id: str,
        *,
        timeout_s: int = 900,
        poll_every_s: float = 5.0,
    ) -> VideoJob:
        elapsed = 0.0
        job: VideoJob | None = None
        while elapsed < timeout_s:
            job = await self.get_video(video_id)
            if job.status in ("complete", "completed", "succeeded"):
                return job
            if job.status in ("failed", "cancelled", "errored"):
                raise MirageError(f"video {video_id} {job.status}: {job.error}")
            await asyncio.sleep(poll_every_s)
            elapsed += poll_every_s
        raise MirageError(
            f"video {video_id} did not complete in {timeout_s}s "
            f"(last status: {(job.status if job else 'unknown')})"
        )

    async def download_video(
        self,
        video_id: str,
        out_path: pathlib.Path,
    ) -> pathlib.Path:
        """GET /v1/videos/{video_id}/content — Mirage 307s to a GCS signed
        URL, so we follow redirects automatically."""
        url = f"{self._base}/v1/videos/{video_id}/content"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            r = await client.get(
                url, headers={"x-api-key": self._api_key},
            )
            r.raise_for_status()
            out_path.write_bytes(r.content)
        log.info(
            "mirage.video.downloaded",
            video_id=video_id, path=str(out_path),
            size_kb=out_path.stat().st_size // 1024,
        )
        return out_path

    # ----- One-shot helpers --------------------------------------------

    async def text_to_clip(
        self,
        *,
        voice_id: str,
        image_path: pathlib.Path,
        script_text: str,
        out_path: pathlib.Path,
        wait_timeout_s: int = 900,
    ) -> VideoJob:
        """End-to-end: text → MP4 via TTS + lipsync.

        Requires a Mirage voice_id from a cloned voice (no stock catalog).
        Mirror of HeyGenClient.create_short_clip().
        """
        t0 = time.time()
        audio = await self.tts(text=script_text, voice_id=voice_id)
        video_id = await self.create_video(
            image_path=image_path, audio_bytes=audio, audio_filename="speech.wav",
        )
        job = await self.wait_for_video(video_id, timeout_s=wait_timeout_s)
        await self.download_video(video_id, out_path)
        log.info(
            "mirage.text_to_clip.done",
            video_id=video_id,
            wall_s=round(time.time() - t0, 1),
        )
        return job

    async def audio_to_clip(
        self,
        *,
        image_path: pathlib.Path,
        audio_path: pathlib.Path,
        out_path: pathlib.Path,
        wait_timeout_s: int = 900,
    ) -> VideoJob:
        """Lipsync-only path: caller provides the audio (any WAV/MP3) and we
        skip Mirage TTS entirely.

        Useful when the account has no cloned voice (Mirage TTS is
        voice-clone-only) — we can reuse audio from a HeyGen render or
        any other TTS provider and isolate the lipsync engine for A/B.
        """
        t0 = time.time()
        audio_path = pathlib.Path(audio_path)
        if not audio_path.exists():
            raise MirageError(f"audio file not found: {audio_path}")
        video_id = await self.create_video(
            image_path=image_path,
            audio_bytes=audio_path.read_bytes(),
            audio_filename=audio_path.name,
        )
        job = await self.wait_for_video(video_id, timeout_s=wait_timeout_s)
        await self.download_video(video_id, out_path)
        log.info(
            "mirage.audio_to_clip.done",
            video_id=video_id,
            wall_s=round(time.time() - t0, 1),
        )
        return job
