"""CLI entry point for ai-ugc-agent.

Today: scaffold + HeyGen client probe. Real `make` command lands once
script_writer / variants / producer are in.

Usage:
  ai-ugc-agent heygen-probe         # list avatars + voices on the API key
  ai-ugc-agent make --brief ...     # (coming soon) full ad generation
"""
from __future__ import annotations

import asyncio
import json
import sys

import structlog
import typer

from ugc import __version__
from ugc.config import settings

app = typer.Typer(no_args_is_help=True, help=__doc__)
log = structlog.get_logger("ugc")


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(f"ai-ugc-agent {__version__}")


@app.command("heygen-probe")
def heygen_probe(
    avatars_only: bool = typer.Option(False, "--avatars-only"),
    voices_only: bool = typer.Option(False, "--voices-only"),
) -> None:
    """List avatars + voices available on the HeyGen account.

    Use this once after pasting HEYGEN_API_KEY to pick which avatar /
    voice you want as the default for your briefs.
    """
    from ugc.integrations.heygen import HeyGenClient

    async def _run() -> None:
        c = HeyGenClient()
        out: dict = {}
        if not voices_only:
            avatars = await c.list_avatars()
            out["avatars"] = [
                {
                    # v3 returns `id` and `name` (not `avatar_id` / `avatar_name`).
                    # Each avatar group bundles a `default_voice_id`.
                    "avatar_id": a.get("id") or a.get("avatar_id"),
                    "avatar_name": a.get("name") or a.get("avatar_name"),
                    "default_voice_id": a.get("default_voice_id"),
                    "gender": a.get("gender"),
                    "looks_count": a.get("looks_count"),
                    "preview": a.get("preview_image_url"),
                }
                for a in avatars[:50]
            ]
        if not avatars_only:
            voices = await c.list_voices()
            out["voices"] = [
                {
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "language": v.get("language"),
                    "gender": v.get("gender"),
                }
                for v in voices[:50]
            ]
        typer.echo(json.dumps(out, indent=2))

    asyncio.run(_run())


@app.command("mirage-probe")
def mirage_probe(
    voice_id: str = typer.Option("", "--voice-id",
        help="Voice id to test TTS with. If empty, just verifies API key auth."),
    text: str = typer.Option(
        "Stop reading overall ROAS. It hides the bleeding half of your spend.",
        "--text",
    ),
    out: str = typer.Option("output/mirage_probe.wav", "--out"),
) -> None:
    """Verify the captions.ai/Mirage API key and (optionally) test TTS.

    With --voice-id: hits POST /v1/audio/text-to-speech/{voice_id} and
    saves the audio to --out, confirming both auth and that the voice id
    is valid for your account.

    Without --voice-id: hits GET /v1/videos to confirm the key is live
    (returns the empty list on a fresh account).
    """
    import pathlib

    from ugc.integrations.mirage import MirageClient

    async def _run() -> None:
        c = MirageClient()
        if not voice_id:
            # Auth-only probe: list videos.
            data = await c._request_json("GET", "/v1/videos", params={"limit": 5})
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("data") or data.get("videos") or []
            else:
                items = []
            typer.echo(
                f"\n✓ Mirage auth OK. /v1/videos returned {len(items)} item(s). "
                "Pass --voice-id to also test TTS."
            )
            if items:
                import json as _j
                typer.echo("\nMost recent:")
                for v in items[:3]:
                    typer.echo(_j.dumps({
                        "id": v.get("id"),
                        "status": v.get("status"),
                        "created_at": v.get("created_at"),
                    }))
            return
        out_path = pathlib.Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        audio = await c.tts(text=text, voice_id=voice_id)
        out_path.write_bytes(audio)
        typer.echo(
            f"\n✓ TTS OK. {len(audio)} bytes written to {out_path}  voice_id={voice_id}"
        )

    asyncio.run(_run())


@app.command("make-from-brief")
def make_from_brief(
    brief_path: str = typer.Option(..., "--brief", "-b",
        help="Path to brief.yaml — see src/ugc/briefs/example.yaml for the schema"),
    variants: int = typer.Option(1, "--variants", "-n",
        help="How many hook variants to render (capped by len(brief.hook_angles))"),
    target_seconds: int = typer.Option(25, "--seconds", "-s"),
    out_dir: str = typer.Option("", "--out-dir",
        help="Override output directory; defaults to output/<brief>/<timestamp>/"),
    dry_run: bool = typer.Option(False, "--dry-run",
        help="Print the generated prompts without firing HeyGen"),
) -> None:
    """Run the full pipeline: brief.yaml → N HeyGen Video Agent renders, in parallel.

    Each hook_angle in the brief becomes one variant. All variants share the
    same product / audience / pain / cta — only the hook differs, so you can
    A/B test the hook cleanly.
    """
    import asyncio
    import pathlib
    import time

    from ugc.integrations.heygen import HeyGenClient
    from ugc.scripts.brief_loader import load_brief
    from ugc.variants import expand

    brief = load_brief(brief_path)
    pack = expand(brief, target_seconds=target_seconds, limit=variants)

    typer.echo(f"\n{brief.name}: expanding {len(pack)} variant(s)\n")
    for v in pack:
        typer.echo(f"  [{v.index}] {v.hook}")

    if dry_run:
        typer.echo("\n--- DRY RUN — printing prompts ---\n")
        for v in pack:
            typer.echo(f"\n=== variant {v.index} ===")
            typer.echo(v.prompt)
            typer.echo("---")
        return

    # Resolve output dir
    if out_dir:
        out_root = pathlib.Path(out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_root = pathlib.Path("output") / brief.name / ts
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "brief_used.yaml").write_text(
        pathlib.Path(brief_path).read_text(encoding="utf-8"), encoding="utf-8",
    )

    async def _one(client: HeyGenClient, v) -> tuple[int, str, str]:
        import json as _json

        from ugc.scripts.brief_loader import load_brief as _load_brief
        from ugc.scripts.prompt_builder import build_prompt_json

        # Re-derive the JSON for the audit trail (cheap; same inputs as v.prompt).
        brief_for_json = _load_brief(brief_path)
        brief_json = build_prompt_json(
            brief=brief_for_json, hook=v.hook, target_seconds=v.target_seconds,
        )
        out_path = out_root / f"variant_{v.index:02d}.mp4"
        prompt_path = out_root / f"variant_{v.index:02d}.prompt.txt"
        json_path = out_root / f"variant_{v.index:02d}.brief.json"
        prompt_path.write_text(v.prompt, encoding="utf-8")
        json_path.write_text(_json.dumps(brief_json, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            job = await client.prompt_to_ad_mp4(prompt=v.prompt, out_path=out_path)
            return (v.index, "ok", f"{out_path}  ({job.duration_s}s, video_id={job.video_id})")
        except Exception as exc:
            return (v.index, "fail", str(exc)[:300])

    async def _run_all() -> None:
        client = HeyGenClient()
        results = await asyncio.gather(*[_one(client, v) for v in pack])
        typer.echo("\n--- results ---")
        for idx, status, info in sorted(results):
            tag = "✓" if status == "ok" else "✗"
            typer.echo(f"  {tag} variant {idx}: {info}")

    asyncio.run(_run_all())


@app.command("compose-from-brief")
def compose_from_brief(
    brief_path: str = typer.Option(..., "--brief", "-b",
        help="Path to brief.yaml — see src/ugc/briefs/example.yaml"),
    avatar_id: str = typer.Option("", "--avatar-id",
        help="HeyGen avatar URN for talking-head scenes. Defaults to "
             "HEYGEN_DEFAULT_AVATAR_ID env var."),
    voice_id: str = typer.Option("", "--voice-id",
        help="HeyGen voice id. Defaults to HEYGEN_DEFAULT_VOICE_ID env var."),
    variants: int = typer.Option(1, "--variants", "-n",
        help="How many hook variants to render (capped by len(brief.hook_angles))"),
    target_seconds: int = typer.Option(25, "--seconds", "-s"),
    out_dir: str = typer.Option("", "--out-dir",
        help="Override output directory; defaults to output/<brief>/<timestamp>/"),
    dry_run: bool = typer.Option(False, "--dry-run",
        help="Print scene plans + write composition.html without firing "
             "HeyGen or hyperframes."),
    skip_render: bool = typer.Option(False, "--skip-render",
        help="Render avatar clips + write composition.html, but skip the "
             "final `npx hyperframes render` step."),
    engine: str = typer.Option("heygen", "--engine", "-e",
        help="Avatar engine: 'heygen' (default, uses /v2/video/generate) or "
             "'mirage' (captions.ai, uses TTS + lipsync). Both compose into "
             "the same HyperFrames template."),
    actor_image: str = typer.Option("", "--actor-image",
        help="[mirage only] JPEG/PNG of the actor's face. Defaults to "
             "MIRAGE_ACTOR_IMAGE env var."),
) -> None:
    """Hybrid pipeline: avatar clips composed via HyperFrames.

    For each variant: render scenes 1/3/4/6 as avatar clips (engine of
    choice), write a composition.html with the 6-scene structure
    (overlays, captions, CTA URL burn-in), and shell out to hyperframes
    to produce variant_NN.mp4.

    Engines:
      heygen — HEYGEN_API_KEY + --avatar-id (look_id, e.g.
               'Brandon_expressive3_public') + --voice-id required.
      mirage — CAPTIONS_API_KEY + --actor-image (path to JPEG/PNG) +
               --voice-id (Mirage voice from platform.mirage.app)
               required. No avatar catalog: lipsyncs the image to TTS
               audio.

    Common requirements:
      - `npx` on PATH; one-time `mkdir -p .hyperframes && cd .hyperframes
        && npx hyperframes init .` before first use.
    """
    import asyncio
    import pathlib
    import time

    from ugc.compose import write_composition
    from ugc.config import settings as _settings
    from ugc.integrations import hyperframes as hf
    from ugc.integrations.heygen import HeyGenClient
    from ugc.scenes import avatar_scenes, plan_scenes
    from ugc.scripts.brief_loader import load_brief
    from ugc.variants import expand

    s = _settings()
    engine = engine.strip().lower()
    if engine not in ("heygen", "mirage"):
        raise typer.BadParameter(
            f"unknown --engine {engine!r}; expected 'heygen' or 'mirage'."
        )

    if engine == "heygen":
        avatar_id = (avatar_id or s.heygen_default_avatar_id).strip()
        voice_id = (voice_id or s.heygen_default_voice_id).strip()
        if not dry_run and (not avatar_id or not voice_id):
            raise typer.BadParameter(
                "compose-from-brief --engine=heygen needs --avatar-id and "
                "--voice-id (or HEYGEN_DEFAULT_AVATAR_ID / "
                "HEYGEN_DEFAULT_VOICE_ID in .env). Run `ai-ugc-agent "
                "heygen-probe` to list available IDs."
            )
    else:  # mirage
        actor_image_path = (actor_image or s.mirage_actor_image).strip()
        voice_id = (voice_id or s.mirage_default_voice_id).strip()
        if not dry_run and (not actor_image_path or not voice_id):
            raise typer.BadParameter(
                "compose-from-brief --engine=mirage needs --actor-image "
                "(or MIRAGE_ACTOR_IMAGE in .env) and --voice-id (or "
                "MIRAGE_DEFAULT_VOICE_ID in .env). Voice IDs come from "
                "platform.mirage.app — they aren't enumerable via API."
            )
        if not dry_run and not pathlib.Path(actor_image_path).exists():
            raise typer.BadParameter(
                f"actor image not found: {actor_image_path}"
            )
        # avatar_id is unused for mirage; keep the var for log lines.
        avatar_id = f"mirage-actor:{actor_image_path}" if actor_image_path else ""

    brief = load_brief(brief_path)
    pack = expand(brief, target_seconds=target_seconds, limit=variants)

    typer.echo(f"\n{brief.name}: composing {len(pack)} variant(s) via HyperFrames\n")
    for v in pack:
        typer.echo(f"  [{v.index}] {v.hook}")

    # Resolve output dir
    if out_dir:
        out_root = pathlib.Path(out_dir)
    else:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_root = pathlib.Path("output") / brief.name / ts
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "brief_used.yaml").write_text(
        pathlib.Path(brief_path).read_text(encoding="utf-8"), encoding="utf-8",
    )

    import json as _json

    from ugc.scripts.prompt_builder import build_prompt_json

    def _write_brief_json(v) -> pathlib.Path:
        """Write the canonical structured prompt as variant_NN.brief.json."""
        brief_json = build_prompt_json(
            brief=brief, hook=v.hook, target_seconds=v.target_seconds,
        )
        json_path = out_root / f"variant_{v.index:02d}.brief.json"
        json_path.write_text(
            _json.dumps(brief_json, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        return json_path

    if dry_run:
        typer.echo("\n--- DRY RUN — printing scene plans + writing composition.html ---")
        for v in pack:
            scenes = plan_scenes(brief=brief, variant=v, target_seconds=target_seconds)
            typer.echo(f"\n=== variant {v.index}: {v.hook}")
            for sc in scenes:
                payload = sc.spoken_text or f"{sc.block} {sc.block_props}"
                typer.echo(
                    f"  scene {sc.index} [{sc.start:.1f}s..{sc.end:.1f}s] "
                    f"{sc.kind:<7} {payload[:90]}"
                )
            # Stub avatar paths so the .html still renders deterministically
            stub_paths = {
                sc.index: f"./variant_{v.index:02d}_scenes/{sc.index}.mp4"
                for sc in avatar_scenes(scenes)
            }
            html_path = write_composition(
                brief=brief, variant=v, scenes=scenes,
                avatar_clip_paths=stub_paths, out_dir=out_root,
            )
            json_path = _write_brief_json(v)
            typer.echo(f"  wrote: {html_path}")
            typer.echo(f"  wrote: {json_path}")
        return

    if not skip_render and not hf.npx_available():
        raise typer.BadParameter(
            f"`{s.hyperframes_npx_bin}` not found on PATH. Install Node.js "
            "(>=18) so `npx hyperframes …` works, or pass --skip-render to "
            "stop after writing composition.html."
        )

    from ugc.compose import render_variant_mp4, write_variant_project

    async def _one(client, v) -> tuple[int, str, str]:
        scenes = plan_scenes(brief=brief, variant=v, target_seconds=target_seconds)
        a_scenes = avatar_scenes(scenes)
        # HF project dir per variant — index.html + sidecars live here.
        project_dir = out_root / f"variant_{v.index:02d}"
        scenes_dir = project_dir / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        _write_brief_json(v)

        async def _clip(sc) -> tuple[int, pathlib.Path]:
            clip_path = scenes_dir / f"{sc.index}.mp4"
            if engine == "heygen":
                await client.create_short_clip(
                    avatar_id=avatar_id,
                    voice_id=voice_id,
                    script_text=sc.spoken_text,
                    out_path=clip_path,
                )
            else:  # mirage
                await client.text_to_clip(
                    voice_id=voice_id,
                    image_path=pathlib.Path(actor_image_path),
                    script_text=sc.spoken_text,
                    out_path=clip_path,
                )
            return sc.index, clip_path

        try:
            results = await asyncio.gather(*[_clip(sc) for sc in a_scenes])
            # Paths relative to the project dir (where index.html lives).
            avatar_clip_paths = {idx: f"scenes/{idx}.mp4" for idx, _ in results}
            if skip_render:
                write_variant_project(
                    brief=brief, variant=v, scenes=scenes,
                    avatar_clip_paths=avatar_clip_paths, project_dir=project_dir,
                )
                return (v.index, "ok", f"clips+project only: {project_dir}")
            mp4_path = out_root / f"variant_{v.index:02d}.mp4"
            await render_variant_mp4(
                brief=brief, variant=v, scenes=scenes,
                avatar_clip_paths=avatar_clip_paths,
                project_dir=project_dir,
                output_mp4=mp4_path,
            )
            return (v.index, "ok", f"{mp4_path}  (project: {project_dir.name}/)")
        except Exception as exc:
            return (v.index, "fail", str(exc)[:300])

    async def _run_all() -> None:
        if engine == "heygen":
            client = HeyGenClient()
        else:
            from ugc.integrations.mirage import MirageClient
            client = MirageClient()
        results = await asyncio.gather(*[_one(client, v) for v in pack])
        typer.echo("\n--- results ---")
        for idx, status, info in sorted(results):
            tag = "✓" if status == "ok" else "✗"
            typer.echo(f"  {tag} variant {idx}: {info}")

    asyncio.run(_run_all())


@app.command()
def make(
    prompt: str = typer.Option(..., "--prompt", "-p",
        help="Plain-English ad brief. The HeyGen Video Agent does scripting + scene composition."),
    out: str = typer.Option("output/ad.mp4", "--out", "-o"),
) -> None:
    """Generate one production-grade ad via HeyGen Video Agent (multi-scene).

    This uses /v3/video-agents — full marketing-video orchestration with
    scripting, avatar selection, scene composition, and b-roll handled
    by HeyGen. Renders take ~3-15 min vs ~2 min for a single talking
    head, but the output is an actual ad, not a stiff explainer clip.
    """
    import pathlib

    from ugc.integrations.heygen import HeyGenClient

    async def _run() -> None:
        c = HeyGenClient()
        out_path = pathlib.Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        job = await c.prompt_to_ad_mp4(prompt=prompt, out_path=out_path)
        typer.echo(f"\n✓ wrote: {out_path}")
        typer.echo(f"  duration: {job.duration_s}s   video_id: {job.video_id}")

    asyncio.run(_run())


@app.command()
def refine(
    session_id: str = typer.Option(..., "--session-id"),
    message: str = typer.Option(..., "--message", "-m",
        help="Refinement instruction (e.g. 'make the hook punchier')."),
) -> None:
    """Send a refinement message to a running Video Agent session."""
    from ugc.integrations.heygen import HeyGenClient

    async def _run() -> None:
        c = HeyGenClient()
        out = await c.message_video_agent(session_id, content=message)
        import json
        typer.echo(json.dumps(out, indent=2))

    asyncio.run(_run())


@app.command()
def smoke(
    avatar_id: str = typer.Option(..., "--avatar-id"),
    voice_id: str = typer.Option(..., "--voice-id"),
    text: str = typer.Option(
        "Stop reading overall ROAS. It hides the bleeding half of your spend.",
        "--text",
    ),
    out: str = typer.Option("output/smoke.mp4", "--out"),
) -> None:
    """Single-clip /v3/videos render — for talking-head fallback testing.

    For real ad output, use `ai-ugc-agent make --prompt "..."` instead.
    """
    import pathlib

    from ugc.integrations.heygen import HeyGenClient

    async def _run() -> None:
        c = HeyGenClient()
        out_path = pathlib.Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        video_id = await c.create_video(
            avatar_id=avatar_id, voice_id=voice_id, script_text=text,
        )
        job = await c.wait_for_video(video_id)
        await c.download_video(job.video_url, out_path)
        typer.echo(f"\n✓ wrote: {out_path}  duration={job.duration_s}s")

    asyncio.run(_run())


def main() -> int:
    s = settings()  # noqa: F841 — proves config loads at startup
    app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
