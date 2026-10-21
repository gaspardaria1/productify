from enum import Enum
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

# --- enums from contracts/content_pack.schema.json -------------------------
# Declared once as Literal types; the tuples are derived with get_args() so the
# fallback logic in T2 can never drift from what the models accept.

IconHint = Literal[
    "bolt", "shield", "sparkle", "chart", "leaf", "clock",
    "globe", "heart", "lock", "star", "cube", "wave",
]
FontPair = Literal["geometric", "editorial", "technical", "condensed", "humanist", "rounded"]
Radius = Literal["sharp", "soft", "pill"]
Mood = Literal["minimal", "opulent", "loud", "earnest", "corporate", "playful"]

ICON_HINTS: tuple[str, ...] = get_args(IconHint)
FONT_PAIRS: tuple[str, ...] = get_args(FontPair)
RADII: tuple[str, ...] = get_args(Radius)
MOODS: tuple[str, ...] = get_args(Mood)


class Tone(str, Enum):
    vc = "vc"
    luxury = "luxury"
    infomercial = "infomercial"
    kickstarter = "kickstarter"


class Strict(BaseModel):
    # additionalProperties: false in the schema — mirror it here so a model that
    # invents a field fails loudly instead of silently dropping it.
    model_config = ConfigDict(extra="forbid")


class VisionResult(Strict):
    object: str
    quirks: list[str]
    material: str
    condition: str


class Brand(Strict):
    name: str
    slug_hint: str
    personality: str


class Hero(Strict):
    headline: str
    subhead: str
    cta_label: str


class Feature(Strict):
    title: str
    body: str
    icon_hint: IconHint


class PricingTier(Strict):
    tier: str
    price: str
    period: str
    bullets: list[str]
    highlighted: bool


class Testimonial(Strict):
    quote: str
    author: str
    role: str


class CTA(Strict):
    headline: str
    button_label: str
    footnote: str


class Palette(Strict):
    # Hex validity is NOT enforced here. T2 validates in Python and swaps the
    # whole palette for the default, because a partial palette looks broken.
    bg: str
    surface: str
    text: str
    muted: str
    accent: str
    accent_contrast: str


class Theme(Strict):
    palette: Palette
    font_pair: FontPair
    radius: Radius
    mood: Mood


class ContentPack(Strict):
    vision: VisionResult
    brand: Brand
    tagline: str
    hero: Hero
    features: list[Feature]
    pricing: list[PricingTier]
    testimonials: list[Testimonial]
    cta: CTA
    theme: Theme
    logo_prompt: str
