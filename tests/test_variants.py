"""Sanity check: brief loads → expand produces N prompts."""
import pathlib
import textwrap

import pytest

from ugc.scripts.brief_loader import load_brief
from ugc.variants import expand


def _write_brief(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    p = tmp_path / "brief.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_brief_loads(tmp_path):
    p = _write_brief(tmp_path, """
        product:
          name: Test Product
          one_liner: A test product
        audience:
          who: Test users
          pain: They have a pain
        hook_angles:
          - Hook one
          - Hook two
        cta:
          text: Try it
    """)
    b = load_brief(p)
    assert b.product.name == "Test Product"
    assert len(b.hook_angles) == 2
    assert b.style.voice == "confident-operator"  # default


def test_expand_produces_one_variant_per_hook(tmp_path):
    p = _write_brief(tmp_path, """
        product:
          name: X
          one_liner: Y
        audience:
          who: Z
          pain: W
        hook_angles:
          - Hook A
          - Hook B
          - Hook C
        cta:
          text: go
    """)
    b = load_brief(p)
    variants = expand(b, target_seconds=20)
    assert len(variants) == 3
    assert variants[0].hook == "Hook A"
    assert variants[2].index == 3
    # Prompt must include the specific hook line for that variant
    assert "Hook A" in variants[0].prompt
    assert "Hook B" not in variants[0].prompt
    # Format spec / scene structure is in every prompt
    for v in variants:
        assert "9:16" in v.prompt
        assert "HOOK" in v.prompt
        assert "CTA" in v.prompt


def test_expand_respects_limit(tmp_path):
    p = _write_brief(tmp_path, """
        product: {name: X, one_liner: Y}
        audience: {who: Z, pain: W}
        hook_angles: [a, b, c, d, e]
        cta: {text: go}
    """)
    b = load_brief(p)
    assert len(expand(b, limit=2)) == 2


def test_brief_rejects_missing_required(tmp_path):
    p = _write_brief(tmp_path, """
        product: {one_liner: Y}
        audience: {who: Z, pain: W}
        hook_angles: [hook]
        cta: {text: go}
    """)
    with pytest.raises(ValueError):
        load_brief(p)
