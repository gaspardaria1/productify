"""
Step 2: INVENT. One Structured Outputs call turns a VisionResult + Tone into a
complete ContentPack.

One call, not five: a single call sees the whole package at once, so the tagline,
the features and the theme come out agreeing with each other. Five small calls
produce five slightly different companies glued together, and you pay the system
prompt and the latency five times over.

Strict mode does NOT support pattern / minItems / maxItems / minLength / format,
so the counts and the hex colours are asked for in the prompt and enforced here
in Python afterwards.
"""

import json
import logging
import re
import time
from pathlib import Path

from fastapi import HTTPException
from openai import AsyncOpenAI

from app.config import ROOT, settings
from app.models import FONT_PAIRS, MOODS, RADII, ContentPack, Tone, VisionResult
from app.pipeline.prompts import build_content_prompt

log = logging.getLogger("productify")

_MODEL = "gpt-5-mini"
_TIMEOUT_S = 40.0
_SCHEMA_PATH = ROOT / "contracts" / "content_pack.schema.json"
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Partial palettes look broken rather than stylish, so one bad value replaces all
# six. Mirrors app/render/theme.py's DEFAULT_PALETTE.
DEFAULT_PALETTE = {
    "bg": "#0B0F19",
    "surface": "#151B2E",
    "text": "#F3F4F6",
    "muted": "#9CA3AF",
    "accent": "#4F46E5",
    "accent_contrast": "#FFFFFF",
}


def _load_schema() -> dict:
    """Loaded from contracts/ at runtime — never duplicated in Python, so the
    frozen contract stays the single source of truth for the API call."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _fit_count(items: list, n: int, what: str, corrections: list[str]) -> list:
    """Truncate if the model gave too many, pad by repeating the last if too few."""
    if len(items) == n:
        return items
    corrections.append(f"{what}={len(items)}->{n}")
    if len(items) > n:
        return items[:n]
    if not items:
        raise ValueError(f"model returned zero {what}")
    return items + [items[-1]] * (n - len(items))


def _repair(data: dict, corrections: list[str]) -> dict:
    """Everything strict mode cannot express. Mutates and returns `data`."""
    data["features"] = _fit_count(data.get("features") or [], 3, "features", corrections)
    data["pricing"] = _fit_count(data.get("pricing") or [], 3, "pricing", corrections)
    data["testimonials"] = _fit_count(data.get("testimonials") or [], 2, "testimonials", corrections)

    # Exactly one highlighted tier; if zero or several, force the middle one.
    flags = [bool(t.get("highlighted")) for t in data["pricing"]]
    if sum(flags) != 1:
        corrections.append(f"highlighted={sum(flags)}->1")
        for i, tier in enumerate(data["pricing"]):
            tier["highlighted"] = i == 1

    theme = data.setdefault("theme", {})

    palette = theme.get("palette") or {}
    missing = set(DEFAULT_PALETTE) - set(palette)
    bad = [k for k, v in palette.items() if not (isinstance(v, str) and _HEX_RE.match(v))]
    if missing or bad:
        corrections.append(f"palette->default (bad={sorted(bad)} missing={sorted(missing)})")
        theme["palette"] = dict(DEFAULT_PALETTE)

    # font_pair / radius / mood are enums in the schema so they are already safe,
    # but fall back to the first value if something unexpected arrives anyway.
    for key, allowed in (("font_pair", FONT_PAIRS), ("radius", RADII), ("mood", MOODS)):
        if theme.get(key) not in allowed:
            corrections.append(f"{key}={theme.get(key)!r}->{allowed[0]}")
            theme[key] = allowed[0]

    return data


async def _ask_model(client: AsyncOpenAI, prompt: str) -> dict:
    schema = _load_schema()
    response = await client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema["name"],
                "strict": schema["strict"],
                "schema": schema["schema"],
            },
        },
        timeout=_TIMEOUT_S,
    )
    return json.loads(response.choices[0].message.content or "{}")


def _mock_pack(tone: Tone) -> ContentPack:
    """Mock mode reads a hand-written fixture per tone, so the whole app — upload,
    render, gallery, download — runs end to end with no key and no spend. `vision`
    is ignored: each fixture already carries the matching VisionResult."""
    path = ROOT / "fixtures" / f"stapler.{tone.value}.json"
    if not path.exists():
        raise HTTPException(
            status_code=502,
            detail="The model had a bad moment. Try again.",
        )
    return ContentPack.model_validate(json.loads(path.read_text(encoding="utf-8")))


async def generate_content(vision: VisionResult, tone: Tone) -> ContentPack:
    if settings.MOCK:
        return _mock_pack(tone)

    prompt = build_content_prompt(vision, tone)
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    t0 = time.monotonic()
    last_error: Exception | None = None
    for attempt in (1, 2):
        corrections: list[str] = []
        try:
            raw = await _ask_model(client, prompt)
            # The model does not see the vision result as structured data, so pin
            # it to what vision actually observed rather than what the copy claims.
            raw["vision"] = vision.model_dump()
            pack = ContentPack.model_validate(_repair(raw, corrections))
        except Exception as exc:
            last_error = exc
            log.warning(
                "content: attempt %d failed (%s: %s)", attempt, type(exc).__name__, exc
            )
            continue

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.info(
            "content: %dms tone=%s brand=%s corrections=%s",
            elapsed_ms,
            tone.value,
            pack.brand.name,
            ", ".join(corrections) or "none",
        )
        return pack

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.error("content: both attempts failed after %dms (%s)", elapsed_ms, last_error)
    raise HTTPException(status_code=502, detail="The model had a bad moment. Try again.")
