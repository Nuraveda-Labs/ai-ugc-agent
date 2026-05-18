"""Composition rendering — Brief + Variant + scene plan + avatar clips →
final variant_NN.mp4 via HyperFrames.

The HyperFrames CLI takes a *project directory* (not a single .html
file): a folder with index.html + hyperframes.json + meta.json +
package.json. So per variant we lay out:

  <out_dir>/variant_NN/
    index.html               — the composition (rendered from Jinja)
    hyperframes.json         — registry pointer (copied from .hyperframes/)
    meta.json                — id + name + createdAt
    package.json             — pinned hyperframes CLI version
    scenes/
      1.mp4                  — HeyGen avatar clip for scene 1
      3.mp4                  —   "    "    "    "    "    "  3
      4.mp4                  —   "    "    "    "    "    "  4
      6.mp4                  —   "    "    "    "    "    "  6

Then `npx hyperframes render <variant_dir> -o <out_dir>/variant_NN.mp4`
produces the final video.
"""
from __future__ import annotations

import datetime
import json
import pathlib

import jinja2

from ugc.integrations import hyperframes as hf
from ugc.scenes import Scene, total_duration
from ugc.scripts.brief_loader import Brief
from ugc.variants import Variant

_TEMPLATE_NAME = "composition_template.html.j2"
_TEMPLATE_DIR = pathlib.Path(__file__).parent

_VOICE_TO_CAPTION_ENERGY = {
    "scrappy-founder": "hype",
    "analyst-explainer": "tutorial",
    "confident-operator": "corporate",
}

_DEFAULT_WIDTH = 1080
_DEFAULT_HEIGHT = 1920

# Pinned to whatever `npx hyperframes init` writes — keeps composition
# behavior reproducible across machines.
_HF_CLI_VERSION = "0.4.44"
_HF_REGISTRY = "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry"


def _env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=jinja2.select_autoescape(
            enabled_extensions=("html", "j2"),
            default=True,
        ),
        keep_trailing_newline=True,
    )


def _composition_id(brief: Brief, variant: Variant) -> str:
    return f"{brief.name}-variant-{variant.index:02d}"


def render_composition_html(
    *,
    brief: Brief,
    variant: Variant,
    scenes: list[Scene],
    avatar_clip_paths: dict[int, str],
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
) -> str:
    """Render the composition HTML for one variant.

    `avatar_clip_paths` maps scene.index → src URL/path. For the
    project-directory layout these are typically `scenes/N.mp4`
    (relative to the project dir's index.html).
    """
    caption_energy = _VOICE_TO_CAPTION_ENERGY.get(brief.style.voice, "corporate")
    music_asset = brief.music.asset if brief.music else ""
    music_volume = brief.music.volume if brief.music else 0.0
    template = _env().get_template(_TEMPLATE_NAME)
    return template.render(
        brief=brief,
        variant=variant,
        scenes=scenes,
        avatar_clip_paths=avatar_clip_paths,
        composition_id=_composition_id(brief, variant),
        width=width,
        height=height,
        total_duration=total_duration(scenes),
        caption_energy=caption_energy,
        music_asset=music_asset,
        music_volume=music_volume,
    )


def _project_files(*, project_id: str) -> dict[str, str]:
    """Static sidecar files for an HF project directory."""
    return {
        "hyperframes.json": json.dumps(
            {
                "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                "registry": _HF_REGISTRY,
                "paths": {
                    "blocks": "compositions",
                    "components": "compositions/components",
                    "assets": "assets",
                },
            },
            indent=2,
        )
        + "\n",
        "meta.json": json.dumps(
            {
                "id": project_id,
                "name": project_id,
                "createdAt": datetime.datetime.utcnow().isoformat() + "Z",
            },
            indent=2,
        )
        + "\n",
        "package.json": json.dumps(
            {
                "name": "hyperframes",
                "private": True,
                "type": "module",
                "scripts": {
                    "dev": f"npx --yes hyperframes@{_HF_CLI_VERSION} preview",
                    "check": (
                        f"npx --yes hyperframes@{_HF_CLI_VERSION} lint && "
                        f"npx --yes hyperframes@{_HF_CLI_VERSION} validate && "
                        f"npx --yes hyperframes@{_HF_CLI_VERSION} inspect"
                    ),
                    "render": f"npx --yes hyperframes@{_HF_CLI_VERSION} render",
                },
            },
            indent=2,
        )
        + "\n",
    }


def write_variant_project(
    *,
    brief: Brief,
    variant: Variant,
    scenes: list[Scene],
    avatar_clip_paths: dict[int, str],
    project_dir: pathlib.Path,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
) -> pathlib.Path:
    """Materialise the HF project directory for one variant.

    Returns the project_dir path. Caller renders it via
    `hyperframes.render(project_dir, ...)`.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    html = render_composition_html(
        brief=brief, variant=variant, scenes=scenes,
        avatar_clip_paths=avatar_clip_paths, width=width, height=height,
    )
    (project_dir / "index.html").write_text(html, encoding="utf-8")
    for fname, content in _project_files(
        project_id=_composition_id(brief, variant),
    ).items():
        (project_dir / fname).write_text(content, encoding="utf-8")
    return project_dir


# Back-compat alias for tests / older callers that wrote a single .html file.
def write_composition(
    *,
    brief: Brief,
    variant: Variant,
    scenes: list[Scene],
    avatar_clip_paths: dict[int, str],
    out_dir: pathlib.Path,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
) -> pathlib.Path:
    """Write a single variant_NN.composition.html into out_dir.

    Kept for the dry-run path and tests. The real render flow uses
    `write_variant_project()` to lay out a full project directory.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    html = render_composition_html(
        brief=brief, variant=variant, scenes=scenes,
        avatar_clip_paths=avatar_clip_paths, width=width, height=height,
    )
    path = out_dir / f"variant_{variant.index:02d}.composition.html"
    path.write_text(html, encoding="utf-8")
    return path


async def render_variant_mp4(
    *,
    brief: Brief,
    variant: Variant,
    scenes: list[Scene],
    avatar_clip_paths: dict[int, str],
    project_dir: pathlib.Path,
    output_mp4: pathlib.Path,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
    timeout_s: int = 1800,
) -> tuple[pathlib.Path, pathlib.Path]:
    """End-to-end: write project dir → render mp4 via HF.

    Returns (project_dir, mp4_path).
    """
    write_variant_project(
        brief=brief, variant=variant, scenes=scenes,
        avatar_clip_paths=avatar_clip_paths, project_dir=project_dir,
        width=width, height=height,
    )
    await hf.render(project_dir, output_path=output_mp4, timeout_s=timeout_s)
    return project_dir, output_mp4
