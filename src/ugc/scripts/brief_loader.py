"""Load + validate a YAML brief into a typed Brief object.

The brief is the operator-facing surface. Every other module consumes a
Brief — script_writer, prompt_builder, variants, producer.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import yaml


@dataclass
class Product:
    name: str
    one_liner: str
    link: str = ""


@dataclass
class Audience:
    who: str
    pain: str
    unaware_of: str = ""


@dataclass
class CTA:
    text: str
    surface: str = "link"  # link | dm | reply


@dataclass
class Style:
    voice: str = "confident-operator"   # confident-operator | scrappy-founder | analyst-explainer
    pacing: str = "fast"
    tone: str = ""


@dataclass
class Visuals:
    background_color: str = "#0a0a0f"
    accent_color: str = "#00ff88"


@dataclass
class Metrics:
    """Optional headline data point for the social-proof scene (scene 5)."""
    headline: str  # e.g. "1.67× → 4.1×"
    label: str = ""  # e.g. "ROAS, post-segmentation"


@dataclass
class Music:
    """Optional background music track for the composition."""
    asset: str  # path relative to repo root or absolute
    volume: float = 0.25


@dataclass
class Brief:
    product: Product
    audience: Audience
    hook_angles: list[str]
    cta: CTA
    style: Style = field(default_factory=Style)
    visuals: Visuals = field(default_factory=Visuals)
    metrics: Metrics | None = None
    music: Music | None = None
    name: str = ""   # filename stem, set by load_brief

    def __post_init__(self) -> None:
        if not self.hook_angles:
            raise ValueError("brief.hook_angles must contain at least one hook")


def load_brief(path: pathlib.Path | str) -> Brief:
    """Read a YAML file → Brief. Validates required fields."""
    p = pathlib.Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"brief {p}: top-level must be a mapping")

    product_raw = raw.get("product") or {}
    audience_raw = raw.get("audience") or {}
    cta_raw = raw.get("cta") or {}
    style_raw = raw.get("style") or {}
    visuals_raw = raw.get("visuals") or {}
    metrics_raw = raw.get("metrics") or None
    music_raw = raw.get("music") or None
    hooks = raw.get("hook_angles") or []

    return Brief(
        name=p.stem,
        product=Product(
            name=product_raw.get("name", "").strip() or _missing("product.name"),
            one_liner=product_raw.get("one_liner", "").strip() or _missing("product.one_liner"),
            link=(product_raw.get("link") or "").strip(),
        ),
        audience=Audience(
            who=audience_raw.get("who", "").strip() or _missing("audience.who"),
            pain=audience_raw.get("pain", "").strip() or _missing("audience.pain"),
            unaware_of=(audience_raw.get("unaware_of") or "").strip(),
        ),
        hook_angles=[h.strip() for h in hooks if h and h.strip()],
        cta=CTA(
            text=(cta_raw.get("text") or "").strip() or _missing("cta.text"),
            surface=(cta_raw.get("surface") or "link").strip(),
        ),
        style=Style(
            voice=(style_raw.get("voice") or "confident-operator").strip(),
            pacing=(style_raw.get("pacing") or "fast").strip(),
            tone=(style_raw.get("tone") or "").strip(),
        ),
        visuals=Visuals(
            background_color=(visuals_raw.get("background_color") or "#0a0a0f").strip(),
            accent_color=(visuals_raw.get("accent_color") or "#00ff88").strip(),
        ),
        metrics=(
            Metrics(
                headline=(metrics_raw.get("headline") or "").strip()
                or _missing("metrics.headline"),
                label=(metrics_raw.get("label") or "").strip(),
            )
            if isinstance(metrics_raw, dict)
            else None
        ),
        music=(
            Music(
                asset=(music_raw.get("asset") or "").strip() or _missing("music.asset"),
                volume=float(music_raw.get("volume", 0.25)),
            )
            if isinstance(music_raw, dict)
            else None
        ),
    )


def _missing(field: str) -> str:
    raise ValueError(f"brief: required field {field!r} missing")
