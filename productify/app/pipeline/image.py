"""
Step 3: BRAND. One gpt-image-1 call per pitch, maximum.

Never raises and never blocks the response: the page is published with an inline
SVG monogram first, and this runs in a background task that swaps the real logo in
afterwards. gpt-image-1 has tens of seconds of latency and must-have #1 is "under a
minute", so a page that waits for it is a page that misses the target.
"""

import base64
import logging
import time

from openai import AsyncOpenAI

from app import config
from app.config import settings
from app.models import ContentPack
from app.pipeline.prompts import build_logo_prompt

log = logging.getLogger("productify")

_MODEL = "gpt-image-1"
_SIZE = "1024x1024"
_TIMEOUT_S = 90.0


async def generate_logo(pack: ContentPack) -> bytes | None:
    """PNG bytes, or None on any failure or at the cap. Callers treat None as
    logo_status=failed and keep the monogram — the page stays valid either way."""
    if settings.MOCK:
        # No mock logo on purpose: the monogram fallback is what we want to
        # exercise all day, and it is what the page ships with at demo time
        # until the real call lands.
        log.info("logo: MOCK mode, skipping the image call")
        return None

    # Shared spend cap — checked before every image call, without exception.
    if not config.can_call_image():
        log.warning(
            "logo: image call cap reached (%d used), skipping", config.image_calls_used()
        )
        return None

    t0 = time.monotonic()
    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        config.note_image_call()
        response = await client.images.generate(
            model=_MODEL,
            prompt=build_logo_prompt(pack),
            size=_SIZE,
            n=1,
            timeout=_TIMEOUT_S,
        )
        b64 = response.data[0].b64_json
        if not b64:
            log.warning("logo: response carried no image data")
            return None
        logo_bytes = base64.b64decode(b64)
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log.warning(
            "logo: failed after %dms (%s: %s)", elapsed_ms, type(exc).__name__, exc
        )
        return None

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info("logo: %dms %d bytes brand=%s", elapsed_ms, len(logo_bytes), pack.brand.name)
    return logo_bytes
