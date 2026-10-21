import json
import random
import re
import string
from pathlib import Path
from typing import Any

from app.config import ROOT, settings
from app.models import ContentPack

_SUFFIX_ALPHABET = string.ascii_lowercase + string.digits


def slugify(brand_name: str) -> str:
    """clipwell -> clipwell-a3f9k. Two identical brand names never collide."""
    base = re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-") or "pitch"
    suffix = "".join(random.choices(_SUFFIX_ALPHABET, k=5))
    return f"{base}-{suffix}"


def out_dir() -> Path:
    """Anchored to the repo root. An absolute OUT_DIR is honoured as-is, so eval
    scripts can write elsewhere without fighting this."""
    p = Path(settings.OUT_DIR)
    return p if p.is_absolute() else ROOT / p


def pitch_dir(slug: str) -> Path:
    return out_dir() / slug


def save_pitch(
    slug: str,
    pack: ContentPack,
    html: str,
    photo_bytes: bytes,
    meta: dict[str, Any],
) -> Path:
    """Write the four files described in contracts/handoff.md. Safe to call twice —
    the logo re-render overwrites index.html and meta.json in place."""
    d = pitch_dir(slug)
    d.mkdir(parents=True, exist_ok=True)

    pitch = {
        "pack": pack.model_dump(),
        "tone": meta.get("tone"),
        "object": meta.get("object"),
        "created_at": meta.get("created_at"),
        "has_logo": meta.get("logo_status") == "ready",
    }

    (d / "pitch.json").write_text(json.dumps(pitch, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "index.html").write_text(html, encoding="utf-8")
    if photo_bytes:
        (d / "photo.jpg").write_bytes(photo_bytes)
    return d


def photo_path(slug: str) -> Path:
    return pitch_dir(slug) / "photo.jpg"


def html_path(slug: str) -> Path:
    return pitch_dir(slug) / "index.html"


def load_html(slug: str) -> str | None:
    p = html_path(slug)
    return p.read_text(encoding="utf-8") if p.exists() else None


def load_photo(slug: str) -> bytes | None:
    p = photo_path(slug)
    return p.read_bytes() if p.exists() else None


def overwrite_html(slug: str, html: str) -> None:
    """The logo re-render replaces index.html in place. save_pitch is safe to call
    twice, but the background task only has new HTML — not a new photo."""
    html_path(slug).write_text(html, encoding="utf-8")


def update_meta(slug: str, **fields: Any) -> dict[str, Any] | None:
    """Read-modify-write a single pitch's meta.json. Each pitch has its own file,
    so two concurrent uploads touch different files and cannot corrupt each other."""
    meta = load_meta(slug)
    if meta is None:
        return None
    meta.update(fields)
    save_meta(slug, meta)
    return meta


def save_meta(slug: str, meta: dict[str, Any]) -> None:
    (pitch_dir(slug) / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_meta(slug: str) -> dict[str, Any] | None:
    p = pitch_dir(slug) / "meta.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def list_pitches() -> list[dict[str, Any]]:
    """Newest first. Reads the directory fresh on every call — no shared mutable
    state, so two simultaneous uploads cannot corrupt the gallery index."""
    root = out_dir()
    if not root.exists():
        return []
    items = [m for d in root.iterdir() if d.is_dir() if (m := load_meta(d.name))]
    items.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return items
