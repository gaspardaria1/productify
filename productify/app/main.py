import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app import config, storage
from app.config import ROOT, settings
from app.models import ContentPack, Tone, VisionResult
from app.pipeline import content as pipeline_content
from app.pipeline import image as pipeline_image
from app.pipeline import vision as pipeline_vision
from app.render import render_pitch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("productify")

app = FastAPI(title="Productify", version="0.1.0")

# Wide open. Hackathon, one day, local network, no auth.
# allow_credentials must stay False: browsers reject "*" combined with credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Station 2's whole frontend, served from the same origin so no proxy is needed.
# Mounted here at the scaffold so Station 2 never has to edit this file.
app.mount("/web", StaticFiles(directory=ROOT / "web", html=True), name="web")


# --- helpers ---------------------------------------------------------------

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _now_iso() -> str:
    """ISO-8601 UTC with a trailing Z, per contracts/api.md."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _summary(meta: dict[str, Any]) -> dict[str, Any]:
    """The PitchSummary of contracts/api.md. The three URLs are always derived
    from the slug so they can never disagree with it."""
    slug = meta["slug"]
    return {
        "slug": slug,
        "status": meta.get("status", "ready"),
        "logo_status": meta.get("logo_status", "pending"),
        "tone": meta.get("tone", ""),
        "brand": meta.get("brand", ""),
        "tagline": meta.get("tagline", ""),
        "object": meta.get("object", ""),
        "created_at": meta.get("created_at", ""),
        "pitch_url": f"/pitch/{slug}",
        "download_url": f"/pitch/{slug}/download",
        "thumb_url": f"/pitch/{slug}/photo.jpg",
        "elapsed_ms": meta.get("elapsed_ms", 0),
    }


async def _finish_logo(slug: str, pack: ContentPack, photo_bytes: bytes) -> None:
    """Runs after the response has already been sent. Generates the logo, then
    re-renders with it and overwrites index.html. On failure or at the spend cap
    the page keeps its inline SVG monogram and stays perfectly valid."""
    try:
        logo_bytes = await pipeline_image.generate_logo(pack)
        if logo_bytes is None:
            storage.update_meta(slug, logo_status="failed")
            return
        storage.overwrite_html(slug, render_pitch(pack, photo_bytes, logo_bytes))
        (storage.pitch_dir(slug) / "logo.png").write_bytes(logo_bytes)
        storage.update_meta(slug, logo_status="ready")
        log.info("logo: swapped in for slug=%s", slug)
    except Exception:
        # A background task must never take the process down.
        log.warning("logo: background task failed for slug=%s", slug, exc_info=True)
        storage.update_meta(slug, logo_status="failed")


def _seed_gallery() -> None:
    """Render the bundles in fixtures/bundles/ if the gallery is empty, so it is
    never empty on stage. Never allowed to prevent startup."""
    try:
        if storage.list_pitches():
            return
        bundles = ROOT / "fixtures" / "bundles"
        if not bundles.is_dir():
            return
        for d in sorted(p for p in bundles.iterdir() if (p / "bundle.json").exists()):
            bundle = json.loads((d / "bundle.json").read_text(encoding="utf-8"))
            pack = ContentPack.model_validate(bundle["pack"])
            photo = (d / "photo.jpg").read_bytes() if (d / "photo.jpg").exists() else b""
            logo = (d / "logo.png").read_bytes() if (d / "logo.png").exists() else None
            slug = storage.slugify(pack.brand.name)
            meta = {
                "slug": slug,
                "status": "ready",
                "logo_status": "ready" if logo else "failed",
                "tone": bundle.get("tone", ""),
                "brand": pack.brand.name,
                "tagline": pack.tagline,
                "object": pack.vision.object,
                "created_at": _now_iso(),
                "elapsed_ms": 0,
            }
            storage.save_pitch(slug, pack, render_pitch(pack, photo, logo), photo, meta)
            log.info("seeded gallery from bundle %s -> %s", d.name, slug)
    except Exception:
        log.warning("seeding the gallery from fixtures/bundles failed", exc_info=True)


@app.on_event("startup")
async def _on_startup() -> None:
    log.info("productify starting: mock=%s out_dir=%s", settings.MOCK, storage.out_dir())
    _seed_gallery()


# --- routes ----------------------------------------------------------------


@app.get("/")
async def root() -> RedirectResponse:
    """Someone will type the bare host on a phone. Send them to the capture
    screen instead of a 404."""
    return RedirectResponse(url="/web/")


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "mock": settings.MOCK}


@app.get("/api/stats")
async def stats() -> dict:
    items = storage.list_pitches()
    elapsed = [m.get("elapsed_ms") or 0 for m in items if m.get("elapsed_ms")]
    used = config.image_calls_used()
    return {
        "pitches_total": len(items),
        "image_calls_used": used,
        "image_calls_remaining": max(0, settings.MAX_IMAGE_CALLS - used),
        "avg_elapsed_ms": round(sum(elapsed) / len(elapsed)) if elapsed else 0,
    }


@app.post("/api/pitch")
async def create_pitch(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    tone: str = Form(...),
) -> dict:
    if tone not in {t.value for t in Tone}:
        raise HTTPException(status_code=400, detail=f"Unknown tone: {tone!r}")
    if image.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=400, detail="Upload a JPEG or a PNG.")

    photo_bytes = await image.read()
    if not photo_bytes:
        raise HTTPException(status_code=400, detail="That upload was empty. Try again.")
    if len(photo_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="That photo is over 10 MB. Try again.")

    tone_enum = Tone(tone)
    t0 = time.monotonic()

    # Vision never hard-fails the request: analyze_image already falls back
    # internally, and this catch covers anything it does not.
    t_vision = time.monotonic()
    try:
        vision = await pipeline_vision.analyze_image(photo_bytes)
    except Exception:
        log.warning("vision failed outright, using a generic result", exc_info=True)
        vision = VisionResult(
            object="mystery object",
            quirks=["defies classification"],
            material="unknown",
            condition="enigmatic",
        )
    ms_vision = int((time.monotonic() - t_vision) * 1000)

    # Content failure IS a real error — a 502 with a readable message.
    t_content = time.monotonic()
    try:
        pack = await pipeline_content.generate_content(vision, tone_enum)
    except HTTPException:
        raise
    except Exception:
        log.warning("content generation failed", exc_info=True)
        raise HTTPException(status_code=502, detail="The model had a bad moment. Try again.")
    ms_content = int((time.monotonic() - t_content) * 1000)

    # Render and publish immediately with logo_bytes=None. A render failure is a
    # genuine bug and is allowed to raise.
    t_render = time.monotonic()
    html = render_pitch(pack, photo_bytes, None)
    ms_render = int((time.monotonic() - t_render) * 1000)

    slug = storage.slugify(pack.brand.slug_hint or pack.brand.name)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    meta = {
        "slug": slug,
        "status": "ready",
        "logo_status": "pending",
        "tone": tone_enum.value,
        "brand": pack.brand.name,
        "tagline": pack.tagline,
        "object": pack.vision.object,
        "created_at": _now_iso(),
        "elapsed_ms": elapsed_ms,
    }
    storage.save_pitch(slug, pack, html, photo_bytes, meta)

    log.info(
        "pitch slug=%s tone=%s object=%s vision=%dms content=%dms render=%dms total=%dms",
        slug,
        tone_enum.value,
        vision.object,
        ms_vision,
        ms_content,
        ms_render,
        elapsed_ms,
    )

    # The response does not wait for the logo.
    background_tasks.add_task(_finish_logo, slug, pack, photo_bytes)
    return _summary(meta)


@app.get("/api/pitch/{slug}")
async def get_pitch(slug: str) -> dict:
    meta = storage.load_meta(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="No pitch with that slug.")
    return _summary(meta)


@app.get("/api/gallery")
async def gallery() -> dict:
    items = [_summary(m) for m in storage.list_pitches() if m.get("slug")]
    return {"count": len(items), "items": items}


@app.get("/pitch/{slug}", response_class=HTMLResponse)
async def pitch_page(slug: str) -> HTMLResponse:
    html = storage.load_html(slug)
    if html is None:
        raise HTTPException(status_code=404, detail="No pitch with that slug.")
    return HTMLResponse(html)


@app.get("/pitch/{slug}/download", response_class=HTMLResponse)
async def pitch_download(slug: str) -> HTMLResponse:
    html = storage.load_html(slug)
    if html is None:
        raise HTTPException(status_code=404, detail="No pitch with that slug.")
    return HTMLResponse(
        html,
        headers={"Content-Disposition": f'attachment; filename="{slug}.html"'},
    )


@app.get("/pitch/{slug}/photo.jpg")
async def pitch_photo(slug: str) -> Response:
    photo = storage.load_photo(slug)
    if photo is None:
        raise HTTPException(status_code=404, detail="No photo for that slug.")
    return Response(photo, media_type="image/jpeg")
