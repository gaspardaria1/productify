"""
Turns a Theme (palette + font_pair + radius + mood enums) into the CSS custom
properties template.html consumes. This is where four tones become four
companies: mood drives STRUCTURE (padding, shadow, alignment), not just color.
"""

import re

from app.models import Palette, Theme

FONT_PAIRS: dict[str, dict[str, str]] = {
    "geometric": {
        "heading": "'Century Gothic', 'Avenir Next', Futura, -apple-system, 'Segoe UI', sans-serif",
        "body": "-apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
        "heading_weight": "700",
        "body_weight": "400",
        "letter_spacing": "-0.02em",
        "text_transform": "none",
    },
    "editorial": {
        "heading": "Georgia, 'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', serif",
        "body": "'Iowan Old Style', Georgia, 'Times New Roman', serif",
        "heading_weight": "400",
        "body_weight": "400",
        "letter_spacing": "0",
        "text_transform": "none",
    },
    "technical": {
        "heading": "'Cascadia Code', Consolas, 'SF Mono', 'Courier New', monospace",
        "body": "-apple-system, 'Segoe UI', Arial, sans-serif",
        "heading_weight": "600",
        "body_weight": "400",
        "letter_spacing": "-0.01em",
        "text_transform": "uppercase",
    },
    "condensed": {
        "heading": "'Arial Narrow', 'Segoe UI', sans-serif",
        "body": "Arial, 'Segoe UI', sans-serif",
        "heading_weight": "900",
        "body_weight": "700",
        "letter_spacing": "0.01em",
        "text_transform": "uppercase",
    },
    "humanist": {
        "heading": "'Segoe UI', Calibri, 'Nunito Sans', -apple-system, sans-serif",
        "body": "'Segoe UI', Calibri, -apple-system, sans-serif",
        "heading_weight": "700",
        "body_weight": "400",
        "letter_spacing": "0",
        "text_transform": "none",
    },
    "rounded": {
        "heading": "'SF Pro Rounded', 'Segoe UI', -apple-system, sans-serif",
        "body": "'Segoe UI', -apple-system, sans-serif",
        "heading_weight": "800",
        "body_weight": "400",
        "letter_spacing": "0",
        "text_transform": "none",
    },
}

RADIUS_SCALES: dict[str, dict[str, str]] = {
    "sharp": {"card": "2px", "button": "2px", "image": "4px"},
    "soft": {"card": "14px", "button": "10px", "image": "18px"},
    "pill": {"card": "24px", "button": "999px", "image": "20px"},
}

MOOD_STYLES: dict[str, dict[str, str]] = {
    "minimal": {
        "section_padding": "64px 0",
        "heading_scale": "1",
        "shadow": "none",
        "border": "1px solid var(--pf-border)",
        "hero_align": "center",
        "heading_tracking": "-0.01em",
        "cta_container": "1080px",
    },
    "opulent": {
        "section_padding": "96px 0",
        "heading_scale": "1.1",
        "shadow": "none",
        "border": "1px solid var(--pf-border)",
        "hero_align": "center",
        "heading_tracking": "0.04em",
        "cta_container": "1080px",
    },
    "loud": {
        "section_padding": "40px 0",
        "heading_scale": "1.3",
        "shadow": "6px 6px 0 var(--pf-text)",
        "border": "3px solid var(--pf-text)",
        "hero_align": "center",
        "heading_tracking": "0",
        "cta_container": "100%",
    },
    "earnest": {
        "section_padding": "56px 0",
        "heading_scale": "1",
        "shadow": "0 4px 16px rgba(0,0,0,0.06)",
        "border": "1px solid var(--pf-border)",
        "hero_align": "left",
        "heading_tracking": "0",
        "cta_container": "1080px",
    },
    "corporate": {
        "section_padding": "72px 0",
        "heading_scale": "0.95",
        "shadow": "0 2px 8px rgba(0,0,0,0.08)",
        "border": "1px solid var(--pf-border)",
        "hero_align": "left",
        "heading_tracking": "0",
        "cta_container": "1080px",
    },
    "playful": {
        "section_padding": "48px 0",
        "heading_scale": "1.15",
        "shadow": "0 10px 24px rgba(0,0,0,0.12)",
        "border": "none",
        "hero_align": "center",
        "heading_tracking": "0",
        "cta_container": "100%",
    },
}

DEFAULT_PALETTE: dict[str, str] = {
    "bg": "#0B0F19",
    "surface": "#151B2E",
    "text": "#F3F4F6",
    "muted": "#9CA3AF",
    "accent": "#4F46E5",
    "accent_contrast": "#FFFFFF",
}

DEFAULT_THEME = Theme(
    palette=DEFAULT_PALETTE,
    font_pair="geometric",
    radius="soft",
    mood="corporate",
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"not a 6-digit hex color: {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(hex_color: str) -> float:
    def linear(c: int) -> float:
        c_srgb = c / 255
        return c_srgb / 12.92 if c_srgb <= 0.03928 else ((c_srgb + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_rgb(hex_color)
    return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    la, lb = _relative_luminance(hex_a), _relative_luminance(hex_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_contrast(fg: str, bg: str, min_ratio: float = 4.5) -> str:
    """Real WCAG contrast. If fg on bg falls below min_ratio, fall back to
    whichever of black/white contrasts better against bg — a model that
    picks a pale grey accent must not be able to ship unreadable text."""
    try:
        if contrast_ratio(fg, bg) >= min_ratio:
            return fg
    except ValueError:
        pass
    try:
        return "#000000" if contrast_ratio("#000000", bg) >= contrast_ratio("#FFFFFF", bg) else "#FFFFFF"
    except ValueError:
        return "#000000"


def _mix(a: str, b: str, weight: float) -> str:
    """Blend a toward b. weight=0 returns a, weight=1 returns b."""
    try:
        ar, ag, ab = _hex_to_rgb(a)
        br, bg_, bb = _hex_to_rgb(b)
    except ValueError:
        return a
    mixed = (round(c1 + (c2 - c1) * weight) for c1, c2 in ((ar, br), (ag, bg_), (ab, bb)))
    r, g, b = mixed
    return f"#{r:02x}{g:02x}{b:02x}"


def ensure_muted(muted: str, text: str, bg: str) -> str:
    """Secondary text needs a lower floor than body copy — 4.5:1 would erase
    the muted look entirely — but it still has to be readable. Below 3:1 we
    rebuild it by blending the (already corrected) text colour toward the
    background, which stays visibly muted without going invisible."""
    try:
        if contrast_ratio(muted, bg) >= 3.0:
            return muted
    except ValueError:
        pass
    return _mix(ensure_contrast(text, bg), bg, 0.35)


def _darken(hex_color: str, amount: float) -> str:
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except ValueError:
        return hex_color
    r, g, b = (max(0, round(c * (1 - amount))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _rgba(hex_color: str, alpha: float) -> str:
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except ValueError:
        return f"rgba(0,0,0,{alpha})"
    return f"rgba({r},{g},{b},{alpha})"


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _safe_palette(palette: Palette) -> Palette:
    """Station 1 guarantees every palette value is a valid 6-digit hex, but the
    Pydantic model does not enforce it and preview.py renders hand-written
    bundles through the same code. These values are emitted into the <style>
    block with |safe, so a value like '#000</style><script>' would escape the
    block entirely. One bad value replaces the whole palette, matching the rule
    the contract already applies upstream: partial palettes look broken.
    """
    values = palette.model_dump()
    if all(_HEX_RE.match(v) for v in values.values()):
        return palette
    return Palette(**DEFAULT_PALETTE)


def build_css_vars(theme: Theme) -> dict[str, str]:
    p = _safe_palette(theme.palette)
    fonts = FONT_PAIRS.get(theme.font_pair, FONT_PAIRS["geometric"])
    radii = RADIUS_SCALES.get(theme.radius, RADIUS_SCALES["soft"])
    mood = MOOD_STYLES.get(theme.mood, MOOD_STYLES["corporate"])

    text = ensure_contrast(p.text, p.bg)

    return {
        "--pf-bg": p.bg,
        "--pf-surface": p.surface,
        "--pf-text": text,
        "--pf-text-on-surface": ensure_contrast(p.text, p.surface),
        "--pf-muted": ensure_muted(p.muted, p.text, p.bg),
        "--pf-accent": p.accent,
        "--pf-accent-hover": _darken(p.accent, 0.12),
        "--pf-accent-soft": _rgba(p.accent, 0.12),
        "--pf-button-label": ensure_contrast(p.accent_contrast, p.accent),
        # derived from the corrected text, not the raw palette value: a pale
        # text colour would otherwise leave every border invisible
        "--pf-border": _rgba(text, 0.18),
        "--pf-font-heading": fonts["heading"],
        "--pf-font-body": fonts["body"],
        "--pf-heading-weight": fonts["heading_weight"],
        "--pf-body-weight": fonts["body_weight"],
        "--pf-letter-spacing": fonts["letter_spacing"],
        "--pf-text-transform": fonts["text_transform"],
        "--pf-radius-card": radii["card"],
        "--pf-radius-button": radii["button"],
        "--pf-radius-image": radii["image"],
        "--pf-section-padding": mood["section_padding"],
        "--pf-heading-scale": mood["heading_scale"],
        "--pf-shadow": mood["shadow"],
        "--pf-mood-border": mood["border"],
        "--pf-hero-align": mood["hero_align"],
        "--pf-heading-tracking": mood["heading_tracking"],
        "--pf-cta-container": mood["cta_container"],
    }
