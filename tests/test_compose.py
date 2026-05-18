"""Unit tests for the HyperFrames composition path.

These tests cover the deterministic logic — scene planning + Jinja
template rendering — without invoking HeyGen or the `npx hyperframes`
CLI.
"""
from __future__ import annotations

import re

import pytest

from ugc.compose import render_composition_html, write_composition
from ugc.scenes import avatar_scenes, plan_scenes, total_duration
from ugc.scripts.brief_loader import (
    CTA,
    Audience,
    Brief,
    Metrics,
    Music,
    Product,
    Style,
    Visuals,
)
from ugc.variants import Variant, expand


def _minimal_brief(*, with_metrics: bool = False, with_music: bool = False) -> Brief:
    return Brief(
        name="test-brief",
        product=Product(
            name="Glitch Audit",
            one_liner="60-second audit of your Meta + Amazon ads",
            link="example.com/grow",
        ),
        audience=Audience(
            who="DTC founders > $5k/mo on Meta",
            pain="Spend on losing keywords; no time to dig through Ads Manager.",
        ),
        hook_angles=["I almost killed a profitable campaign because of one keyword."],
        cta=CTA(text="Free audit at example.com/grow."),
        style=Style(voice="confident-operator", pacing="fast"),
        visuals=Visuals(),
        metrics=Metrics(headline="1.67× → 4.1×", label="ROAS") if with_metrics else None,
        music=Music(asset="assets/bgm.mp3", volume=0.3) if with_music else None,
    )


def _variant_for(brief: Brief, target_seconds: int = 25) -> Variant:
    return expand(brief, target_seconds=target_seconds, limit=1)[0]


def test_scene_plan_has_six_scenes():
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    assert len(scenes) == 6
    assert [s.kind for s in scenes] == [
        "avatar", "overlay", "avatar", "avatar", "overlay", "avatar",
    ]


def test_scene_plan_durations_sum_to_target_25s():
    brief = _minimal_brief()
    v = _variant_for(brief, target_seconds=25)
    scenes = plan_scenes(brief=brief, variant=v, target_seconds=25)
    assert total_duration(scenes) == pytest.approx(25.0, abs=0.01)


def test_scene_plan_durations_sum_to_target_when_rescaled():
    # 40s target — durations should rescale linearly, last scene ends at 40.
    brief = _minimal_brief()
    v = _variant_for(brief, target_seconds=40)
    scenes = plan_scenes(brief=brief, variant=v, target_seconds=40)
    assert total_duration(scenes) == pytest.approx(40.0, abs=0.01)
    # Scenes are contiguous (no gaps, no overlaps)
    for prev, curr in zip(scenes, scenes[1:], strict=False):
        assert curr.start == pytest.approx(prev.end, abs=0.01)


def test_scene_plan_uses_brief_fields():
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    assert scenes[0].spoken_text == v.hook
    assert brief.cta.text in scenes[5].spoken_text
    assert scenes[5].burn_in_text == brief.product.link


def test_scene_5_falls_back_when_no_metrics():
    brief = _minimal_brief(with_metrics=False)
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    assert scenes[4].kind == "overlay"
    assert scenes[4].block == "social-proof"
    assert scenes[4].block_props["headline"]  # fallback string is non-empty


def test_scene_5_uses_metrics_when_provided():
    brief = _minimal_brief(with_metrics=True)
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    assert scenes[4].block_props["headline"] == "1.67× → 4.1×"
    assert scenes[4].block_props["label"] == "ROAS"


def test_avatar_scenes_filter():
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    a = avatar_scenes(scenes)
    assert [s.index for s in a] == [1, 3, 4, 6]


def test_template_renders_for_minimal_brief():
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    # Required structural attributes from HF prompting rules
    assert 'id="root"' in html
    assert "data-composition-id" in html
    assert 'data-width="1080"' in html
    assert 'data-height="1920"' in html
    assert "window.__timelines" in html
    assert "gsap.timeline" in html
    # HF requires deterministic rendering — no Math.random() calls in the runtime.
    assert "Math.random(" not in html
    # Every timed element must carry class="clip" + data-start + data-duration
    clip_blocks = re.findall(r'<[^>]*class="[^"]*clip[^"]*"[^>]*>', html)
    assert clip_blocks, "expected class='clip' elements in rendered html"
    for block in clip_blocks:
        assert "data-start" in block
        assert "data-duration" in block


def test_template_includes_avatar_clip_srcs():
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    for path in avatar_paths.values():
        assert path in html


def test_template_burns_in_cta_url():
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    assert brief.product.link in html
    assert "url-burn" in html


def test_template_threads_brand_colors():
    brief = _minimal_brief()
    brief.visuals.background_color = "#112233"
    brief.visuals.accent_color = "#aabbcc"
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    assert "#112233" in html
    assert "#aabbcc" in html


def test_template_emits_audio_track_when_music_present():
    brief = _minimal_brief(with_music=True)
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    assert "<audio" in html
    assert brief.music.asset in html


def test_template_omits_audio_track_when_no_music():
    brief = _minimal_brief(with_music=False)
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    assert "<audio" not in html


def test_caption_energy_changes_with_voice():
    # scrappy-founder → "hype" energy → uses accent colour for captions
    brief = _minimal_brief()
    brief.style.voice = "scrappy-founder"
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    hype_html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    assert "84px" in hype_html  # hype caption font-size

    # analyst-explainer → "tutorial" energy → monospace
    brief.style.voice = "analyst-explainer"
    tut_html = render_composition_html(
        brief=brief, variant=v, scenes=scenes, avatar_clip_paths=avatar_paths,
    )
    assert "monospace" in tut_html


def test_write_composition_creates_file(tmp_path):
    brief = _minimal_brief()
    v = _variant_for(brief)
    scenes = plan_scenes(brief=brief, variant=v)
    avatar_paths = {sc.index: f"./scenes/{sc.index}.mp4" for sc in avatar_scenes(scenes)}
    path = write_composition(
        brief=brief, variant=v, scenes=scenes,
        avatar_clip_paths=avatar_paths, out_dir=tmp_path,
    )
    assert path.exists()
    assert path.name == "variant_01.composition.html"
    body = path.read_text(encoding="utf-8")
    assert "<!doctype html>" in body
    assert brief.name in body
