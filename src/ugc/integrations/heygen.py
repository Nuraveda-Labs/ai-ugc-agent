"""HeyGen REST API client (v3).

The v2 /video/generate endpoint produces a SINGLE talking-head clip
(stiff, looks like a corporate explainer). For production-grade UGC
ads we use HeyGen's v3 Video Agent:

  POST /v3/video-agents          — text prompt → full marketing video
                                   (multi-scene, b-roll, scene
                                   composition, avatar selection — all
                                   handled by HeyGen internally)
  GET  /v3/video-agents/{id}     — poll status / get the final video_id
  POST /v3/video-agents/{id}/messages
                                  — iterative refinement: "make scene 2
                                    punchier", "swap the avatar" etc.
                                    BEFORE the final render lands.

We also wrap:
  GET  /v3/avatars               — list stock + custom avatar groups
  GET  /v3/avatar-looks          — variations (outfits / framings)
  POST /v3/avatars               — create a custom avatar from a photo
                                   (Tejas's face → founder-voiced ads)
  POST /v3/assets                — upload an image / video / audio
  POST /v3/videos                — direct single-clip render (legacy
                                   one-shot, retained for compatibility)
  GET  /v3/videos/{id}           — fetch render status / final url

Auth: X-Api-Key header. Base: https://api.heygen.com.
"""
from __future__ import annotations

import asyncio
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


class HeyGenError(RuntimeError):
    """Non-recoverable HeyGen API error."""


class HeyGenRetryableError(HeyGenError):
    """Retryable error (5xx / 429 / network) — tenacity catches it."""


@dataclass
class VideoJob:
    video_id: str
    status: str           # queued | processing | completed | failed
    video_url: str | None = None
    duration_s: float | None = None
    error: str | None = None


class HeyGenClient:
    """Async client. One instance per process is fine; thread-safe via httpx."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        s = settings()
        self._api_key = api_key or s.heygen_api_key
        if not self._api_key:
            raise HeyGenError("HEYGEN_API_KEY not set")
        self._base = (api_base or s.heygen_api_base).rstrip("/")

    # ----- HTTP plumbing --------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((httpx.HTTPError, HeyGenRetryableError)),
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.request(
                method, url, headers=self._headers(),
                params=params, json=json,
            )
        if resp.status_code in (429, 500, 502, 503, 504):
            raise HeyGenRetryableError(
                f"{method} {path} -> {resp.status_code} (retryable): {resp.text[:300]}"
            )
        if resp.status_code >= 400:
            raise HeyGenError(
                f"{method} {path} -> {resp.status_code}: {resp.text[:500]}"
            )
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    # ----- Catalog endpoints (v3) ----------------------------------------

    async def list_avatars(self, *, limit: int = 50) -> list[dict]:
        """GET /v3/avatars — list avatar groups (a "group" = one character with
        many "looks"; use list_avatar_looks for the actual usable URNs).

        Note: HeyGen caps `limit` at 50 — passing >50 returns 400. Response
        shape varies by account: sometimes {data: {avatars: [...]}},
        sometimes {data: [...]}, sometimes a bare list.
        """
        data = await self._request(
            "GET", "/v3/avatars", params={"limit": min(limit, 50)},
        )
        if isinstance(data, list):
            return data
        inner = data.get("data")
        if isinstance(inner, list):
            return inner
        if isinstance(inner, dict):
            return inner.get("avatars") or []
        return data.get("avatars") or []

    async def list_avatar_looks(
        self, *, avatar_group_id: str | None = None, limit: int = 50,
    ) -> list[dict]:
        """GET /v3/avatar-looks — outfits/framings per character. limit≤50."""
        params: dict = {"limit": min(limit, 50)}
        if avatar_group_id:
            params["avatar_group_id"] = avatar_group_id
        data = await self._request("GET", "/v3/avatar-looks", params=params)
        return (data.get("data") or {}).get("looks") or data.get("looks") or []

    # Voices were a v2 concept; v3 bundles them with avatars. Kept for
    # back-compat where callers expect the old shape.
    async def list_voices(self) -> list[dict]:
        data = await self._request("GET", "/v2/voices")
        return (data.get("data") or {}).get("voices") or []

    # ----- Video Agent (the production primitive) ------------------------

    async def create_video_agent_session(
        self,
        *,
        prompt: str,
    ) -> dict:
        """POST /v3/video-agents — kick off a multi-scene marketing-video
        generation. The agent handles scripting, scene planning, b-roll
        selection, avatar selection, and final render internally.

        Returns the raw response: {session_id, status, video_id?, ...}.
        """
        data = await self._request(
            "POST", "/v3/video-agents", json={"prompt": prompt},
        )
        # Some accounts get the session at top-level, some under data{}
        payload = data.get("data") or data
        session_id = payload.get("session_id")
        if not session_id:
            raise HeyGenError(
                f"create_video_agent_session: no session_id in response: {data}"
            )
        log.info(
            "heygen.video_agent.queued",
            session_id=session_id,
            prompt_chars=len(prompt),
        )
        return payload

    async def get_video_agent_session(self, session_id: str) -> dict:
        """GET /v3/video-agents/{session_id}."""
        data = await self._request("GET", f"/v3/video-agents/{session_id}")
        return data.get("data") or data

    async def message_video_agent(
        self, session_id: str, *, content: str,
    ) -> dict:
        """POST /v3/video-agents/{session_id}/messages — iterative refine
        ("make scene 2 punchier", "swap the avatar"). Use BEFORE the
        final render to nudge the agent."""
        data = await self._request(
            "POST",
            f"/v3/video-agents/{session_id}/messages",
            json={"content": content},
        )
        return data.get("data") or data

    async def stop_video_agent(self, session_id: str) -> dict:
        """POST /v3/video-agents/{session_id}/stop — halt at next checkpoint."""
        data = await self._request(
            "POST", f"/v3/video-agents/{session_id}/stop",
        )
        return data.get("data") or data

    async def wait_for_video_agent(
        self,
        session_id: str,
        *,
        timeout_s: int = 1800,
        poll_every_s: float = 8.0,
    ) -> dict:
        """Poll the agent session until it produces a video_id (then poll
        the video itself), times out, or fails. Returns the completed
        video session dict."""
        elapsed = 0.0
        last: dict = {}
        while elapsed < timeout_s:
            last = await self.get_video_agent_session(session_id)
            status = str(last.get("status", "unknown")).lower()
            video_id = last.get("video_id")
            if status in ("completed", "succeeded", "done") and video_id:
                log.info(
                    "heygen.video_agent.completed",
                    session_id=session_id, video_id=video_id,
                )
                return last
            if status in ("failed", "errored", "stopped"):
                raise HeyGenError(
                    f"video agent {session_id} {status}: {last.get('error') or last}"
                )
            await asyncio.sleep(poll_every_s)
            elapsed += poll_every_s
        raise HeyGenError(
            f"video agent {session_id} did not complete in {timeout_s}s "
            f"(last status: {last.get('status')})"
        )

    # ----- Direct single-clip render (v3 — for talking-head fallbacks) ---

    async def create_video(
        self,
        *,
        avatar_id: str,
        script_text: str,
        voice_id: str,
        width: int = 1080,
        height: int = 1920,
        title: str = "",
        avatar_style: str = "normal",
    ) -> str:
        """POST /v2/video/generate — single-clip avatar render. Returns video_id.

        We use the v2 endpoint (not /v3/videos) because the v3 schema is
        a strict discriminated union that 400s on missing optional fields;
        v2 is the documented stable surface for direct talking-head renders.
        """
        body = {
            "title": title or script_text[:80],
            "caption": False,
            "dimension": {"width": width, "height": height},
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": avatar_style,
                    },
                    "voice": {
                        "type": "text",
                        "input_text": script_text,
                        "voice_id": voice_id,
                    },
                }
            ],
        }
        data = await self._request("POST", "/v2/video/generate", json=body)
        d = data.get("data") or data
        video_id = d.get("video_id") or d.get("id")
        if not video_id:
            raise HeyGenError(f"create_video: no video_id: {data}")
        return video_id

    async def get_video(self, video_id: str) -> VideoJob:
        """GET /v1/video_status.get — pairs with /v2/video/generate."""
        data = await self._request(
            "GET", "/v1/video_status.get", params={"video_id": video_id},
        )
        d = data.get("data") or data
        return VideoJob(
            video_id=video_id,
            status=str(d.get("status", "unknown")).lower(),
            video_url=d.get("video_url") or d.get("url"),
            duration_s=d.get("duration"),
            error=(d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else d.get("error"),
        )

    async def wait_for_video(
        self,
        video_id: str,
        *,
        timeout_s: int = 600,
        poll_every_s: float = 5.0,
    ) -> VideoJob:
        elapsed = 0.0
        job: VideoJob | None = None
        while elapsed < timeout_s:
            job = await self.get_video(video_id)
            if job.status in ("completed", "succeeded"):
                return job
            if job.status in ("failed", "errored"):
                raise HeyGenError(f"video {video_id} failed: {job.error}")
            await asyncio.sleep(poll_every_s)
            elapsed += poll_every_s
        raise HeyGenError(
            f"video {video_id} did not complete in {timeout_s}s "
            f"(last status: {(job.status if job else 'unknown')})"
        )

    async def download_video(
        self, video_url: str, out_path: pathlib.Path,
    ) -> pathlib.Path:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.get(video_url)
            r.raise_for_status()
            out_path.write_bytes(r.content)
        log.info(
            "heygen.video.downloaded",
            path=str(out_path),
            size_kb=out_path.stat().st_size // 1024,
        )
        return out_path

    # ----- One-shot helper: script → mp4 (compose-from-brief pipeline) ---

    async def create_short_clip(
        self,
        *,
        avatar_id: str,
        voice_id: str,
        script_text: str,
        out_path: pathlib.Path,
        width: int = 1080,
        height: int = 1920,
        wait_timeout_s: int = 600,
    ) -> VideoJob:
        """Render a single talking-head clip, wait for it, download to disk.

        Used by the HyperFrames composition pipeline — each avatar scene
        is one of these. Composes the existing create_video → wait_for_video
        → download_video chain into one awaitable so callers can fan
        out scenes via asyncio.gather.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        video_id = await self.create_video(
            avatar_id=avatar_id,
            voice_id=voice_id,
            script_text=script_text,
            width=width,
            height=height,
        )
        job = await self.wait_for_video(video_id, timeout_s=wait_timeout_s)
        if not job.video_url:
            raise HeyGenError(f"clip {video_id} completed without url")
        await self.download_video(job.video_url, out_path)
        return job

    # ----- Custom avatar from photo (Tejas's actual face) ----------------

    async def upload_asset(self, file_path: pathlib.Path) -> str:
        """POST /v3/assets — upload image/video/audio. Returns asset_id."""
        s = settings()
        url = f"{self._base}/v3/assets"
        async with httpx.AsyncClient(timeout=120) as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    url,
                    headers={"X-Api-Key": s.heygen_api_key},
                    files={"file": (file_path.name, f.read())},
                )
        if resp.status_code >= 400:
            raise HeyGenError(f"upload_asset {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        asset_id = (data.get("data") or {}).get("asset_id") or data.get("asset_id")
        if not asset_id:
            raise HeyGenError(f"upload_asset: no asset_id in response: {data}")
        return asset_id

    async def create_avatar_from_photo(
        self,
        *,
        asset_id: str,
        name: str,
    ) -> dict:
        """POST /v3/avatars (type=photo). One-time setup; HeyGen takes
        ~24h to train. After approval the avatar is available in
        list_avatars() and usable in any subsequent render."""
        body = {
            "type": "photo",
            "name": name,
            "asset_id": asset_id,
        }
        data = await self._request("POST", "/v3/avatars", json=body)
        return data.get("data") or data

    # ----- Convenience: prompt → mp4 via the full Video Agent pipeline ---

    async def prompt_to_ad_mp4(
        self,
        *,
        prompt: str,
        out_path: pathlib.Path,
        wait_timeout_s: int = 1800,
    ) -> VideoJob:
        """End-to-end production-grade ad generation.

        prompt: full ad brief in plain English. The agent does scripting,
                avatar choice, scene composition, and renders the mp4.

        Returns the completed VideoJob (with .video_url + .duration_s).
        """
        t0 = time.time()
        session = await self.create_video_agent_session(prompt=prompt)
        session_id = session["session_id"]
        completed = await self.wait_for_video_agent(
            session_id, timeout_s=wait_timeout_s,
        )
        video_id = completed.get("video_id")
        if not video_id:
            raise HeyGenError(f"agent completed without video_id: {completed}")

        # Fetch the actual video record + download
        job = await self.wait_for_video(video_id, timeout_s=600)
        if not job.video_url:
            raise HeyGenError(f"completed video has no url: {job}")
        await self.download_video(job.video_url, out_path)
        log.info(
            "heygen.prompt_to_ad_mp4.done",
            session_id=session_id,
            video_id=video_id,
            duration_s=job.duration_s,
            wall_s=round(time.time() - t0, 1),
        )
        return job
