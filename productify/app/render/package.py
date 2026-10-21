"""
Single-file packaging: turns a rendered HTML string plus raw photo/logo bytes
into one self-contained document, and asserts that it stays that way. No
external requests may survive — the page has to open with the network cable
pulled and open offline from a downloaded file.
"""

import base64
import html
import io
import re

from PIL import Image, ImageOps

MAX_PHOTO_EDGE = 1200
PHOTO_JPEG_QUALITY = 82
MAX_LOGO_EDGE = 256

ICON_SVGS: dict[str, str] = {
    "bolt": '<path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>',
    "shield": '<path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"/>',
    "sparkle": '<path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2z"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M2 20h20"/>',
    "leaf": '<path d="M5 21c8 0 14-6 14-14V5h-2C9 5 3 11 3 19v2h2z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 4 6 4 9s-1.5 6.5-4 9c-2.5-2.5-4-6-4-9s1.5-6.5 4-9z"/>',
    "heart": '<path d="M12 20s-7-4.5-9.5-9C.8 7.5 2 4 5.5 4c2 0 3.5 1.2 4.5 2.7C11 5.2 12.5 4 14.5 4 18 4 19.2 7.5 21.5 11 19 15.5 12 20 12 20z"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "star": '<path d="M12 2l3 7h7l-5.5 4.5L18.5 21 12 16.5 5.5 21 7.5 13.5 2 9h7z"/>',
    "cube": '<path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M3 7l9 5 9-5M12 12v10"/>',
    "wave": '<path d="M2 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0"/><path d="M2 18c2-3 4-3 6 0s4 3 6 0 4-3 6 0"/>',
    "_fallback": '<circle cx="12" cy="12" r="5"/>',
}


def icon_svg(icon_hint: str) -> str:
    inner = ICON_SVGS.get(icon_hint, ICON_SVGS["_fallback"])
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{inner}</svg>'
    )


def embed_photo(photo_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(photo_bytes))
    # Phone photos are usually stored landscape with an EXIF Orientation tag.
    # Re-encoding drops that tag, so the rotation has to be baked into the
    # pixels here or a portrait photo ships sideways.
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=PHOTO_JPEG_QUALITY)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def _initials(brand_name: str) -> str:
    words = [w for w in re.split(r"\s+", brand_name.strip()) if w]
    letters = [w[0].upper() for w in words if w[0].isalnum()]
    return "".join(letters[:2]) or "?"


def monogram_svg(brand_name: str, accent: str, accent_contrast: str) -> str:
    # _initials() already strips this to at most two alphanumerics, so it is
    # safe to interpolate; the colours are escaped defensively because these
    # strings are handed to the template with |safe.
    initials = _initials(brand_name)
    accent = html.escape(accent, quote=True)
    accent_contrast = html.escape(accent_contrast, quote=True)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<rect width="100" height="100" rx="20" fill="{accent}"/>'
        f'<text x="50" y="64" font-size="42" font-family="sans-serif" '
        f'font-weight="700" text-anchor="middle" fill="{accent_contrast}">{initials}</text>'
        "</svg>"
    )


def monogram_data_uri(brand_name: str, accent: str, accent_contrast: str) -> str:
    svg = monogram_svg(brand_name, accent, accent_contrast)
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{data}"


def embed_logo_markup(brand_name: str, accent: str, accent_contrast: str, logo_bytes: bytes | None) -> str:
    """Real logo if we have one, otherwise an inline SVG monogram — the page
    must look finished before Station 1's async logo call lands."""
    # The template renders this with |safe, so autoescape does not apply here.
    # brand_name came out of a language model and may contain quotes or tags:
    # escape it explicitly or it breaks out of the attribute.
    alt = html.escape(f"{brand_name} logo", quote=True)
    if logo_bytes:
        img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
        img.thumbnail((MAX_LOGO_EDGE, MAX_LOGO_EDGE))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        return f'<img class="pf-logo" src="data:image/png;base64,{data}" alt="{alt}">'
    svg = monogram_svg(brand_name, accent, accent_contrast)
    return f'<span class="pf-logo pf-logo-monogram" role="img" aria-label="{alt}">{svg}</span>'


_ASSET_ATTR_RE = re.compile(
    # double-quoted, single-quoted, or bare — a future edit using single quotes
    # must not slip past the only check enforcing the offline guarantee.
    r'(?:src|srcset|href|poster|data-src)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))',
    re.IGNORECASE,
)
_URL_FN_RE = re.compile(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', re.IGNORECASE)
_IMPORT_RE = re.compile(r'@import\s+(?:url\()?[\'"]?([^\'")\s;]+)', re.IGNORECASE)


def assert_self_contained(page_html: str) -> None:
    """Scan every src=, href=, url() and @import value; raise if anything
    isn't data:, a same-page #anchor, or empty. Fail loudly rather than ship a
    page that breaks the moment it's opened offline on stage.

    The parameter is deliberately not named `html` — that would shadow the
    stdlib module this file imports for escaping.
    """
    matches = (
        list(_ASSET_ATTR_RE.finditer(page_html))
        + list(_URL_FN_RE.finditer(page_html))
        + list(_IMPORT_RE.finditer(page_html))
    )
    for match in matches:
        # _ASSET_ATTR_RE has three alternatives (double/single/bare quoted), so
        # take whichever group actually captured rather than assuming group 1.
        value = next((g for g in match.groups() if g is not None), "").strip()
        if not value:
            continue
        if value.startswith("data:") or value.startswith("#"):
            continue
        raise ValueError(f"pitch page is not self-contained: found external reference {value!r}")
