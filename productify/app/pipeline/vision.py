import base64
import io
import json
import logging
import time

from openai import AsyncOpenAI
from PIL import Image

from app.config import settings
from app.models import VisionResult
from app.pipeline.prompts import build_vision_prompt

log = logging.getLogger("productify")

_MAX_EDGE = 1024
_TIMEOUT_S = 25.0

# The demo must never hard-fail. If both the real attempt and the retry fail,
# this is what a "vision failure" looks like on the page instead of a stack trace.
_FALLBACK = VisionResult(
    object="mystery object",
    quirks=["defies classification"],
    material="unknown",
    condition="enigmatic",
)


def _to_data_url(photo_bytes: bytes) -> str:
    """Downscale to 1024px on the long edge before encoding. The client resizes
    too, but never trust the client — a phone can still hand us a 12MP original."""
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    w, h = img.size
    scale = _MAX_EDGE / max(w, h)
    if scale < 1:
        img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


async def _ask_model(client: AsyncOpenAI, data_url: str, prompt: str) -> VisionResult:
    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        response_format={"type": "json_object"},
        timeout=_TIMEOUT_S,
    )
    raw = response.choices[0].message.content or "{}"
    return VisionResult.model_validate(json.loads(raw))


async def analyze_image(photo_bytes: bytes) -> VisionResult:
    if settings.MOCK:
        return VisionResult(
            object="stapler",
            quirks=["a scratch across the lid", "a half-peeled price sticker on the base"],
            material="brushed steel",
            condition="well-loved",
        )

    data_url = _to_data_url(photo_bytes)
    prompt = build_vision_prompt()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    t0 = time.monotonic()
    try:
        result = await _ask_model(client, data_url, prompt)
    except Exception as first_error:
        log.warning("vision: first attempt failed (%s), retrying once", type(first_error).__name__)
        stricter = prompt + "\n\nReturn ONLY the JSON object. Nothing before it, nothing after it."
        try:
            result = await _ask_model(client, data_url, stricter)
        except Exception as second_error:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            log.warning(
                "vision: retry also failed (%s) after %dms — falling back",
                type(second_error).__name__,
                elapsed_ms,
            )
            return _FALLBACK

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info("vision: %dms object=%s", elapsed_ms, result.object)
    return result
