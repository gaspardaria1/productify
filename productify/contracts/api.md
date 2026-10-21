# API contract — FROZEN

Agreed at minute 30. Any change must be announced out loud to the whole team and made by
one person only. Lane C builds against this and must not have to guess.

Base URL in development: `http://localhost:8000`

## Enums

```
tone         : "vc" | "luxury" | "infomercial" | "kickstarter"
status       : "pending" | "ready" | "failed"
logo_status  : "pending" | "ready" | "failed"
```

Tone display labels (frontend only, backend never sends these):

| value | label |
|---|---|
| `vc` | Silicon Valley startup |
| `luxury` | Luxury brand |
| `infomercial` | Late-night infomercial |
| `kickstarter` | Kickstarter campaign |

## `PitchSummary` — the shared object shape

Every endpoint that returns a pitch returns exactly this:

```json
{
  "slug": "clipwell-a3f9k",
  "status": "ready",
  "logo_status": "pending",
  "tone": "vc",
  "brand": "ClipWell",
  "tagline": "The last stapler you will ever onboard.",
  "object": "stapler",
  "created_at": "2026-08-11T09:41:02Z",
  "pitch_url": "/pitch/clipwell-a3f9k",
  "download_url": "/pitch/clipwell-a3f9k/download",
  "thumb_url": "/pitch/clipwell-a3f9k/photo.jpg",
  "elapsed_ms": 18420
}
```

`created_at` is ISO-8601 UTC with a trailing `Z`.

---

## `POST /api/pitch`

Creates a pitch. Returns as soon as the page exists — **does not wait for the logo.**

**Request:** `multipart/form-data`

| field | type | notes |
|---|---|---|
| `image` | file | JPEG or PNG. Max 10 MB. Client should resize to ≤1280px first. |
| `tone` | string | one of the tone enum values |

**200:** a `PitchSummary` with `status: "ready"` and `logo_status: "pending"`.

**Errors:**
```json
{ "detail": "Human-readable message safe to show the user." }
```
| code | when |
|---|---|
| 400 | missing/invalid `image`, unsupported content type, over 10 MB, invalid `tone` |
| 502 | the content model failed twice — message: "The model had a bad moment. Try again." |
| 503 | image spend cap reached (the page is still created; this is not returned for logos) |

---

## `GET /api/pitch/{slug}`

Poll this to find out when the logo has landed.

**200:** a `PitchSummary`. **404** if the slug does not exist.

Frontend polls every 1.5s, giving up after 40s, until `logo_status` is `ready` or `failed`.
The page is already usable while `logo_status` is `pending` — it shows an inline SVG
monogram in place of the logo.

---

## `GET /api/gallery`

**200:**
```json
{
  "count": 12,
  "items": [ { "...PitchSummary..." } ]
}
```
Newest first. No pagination — it is one day.

---

## `GET /pitch/{slug}`

**200:** `text/html` — the complete self-contained page. **404** if unknown.

## `GET /pitch/{slug}/download`

**200:** the same HTML with `Content-Disposition: attachment; filename="{slug}.html"`.

## `GET /pitch/{slug}/photo.jpg`

**200:** `image/jpeg` — the uploaded photo, resized. Used as the gallery thumbnail.

---

## `GET /health`

```json
{ "ok": true, "mock": true }
```

## `GET /api/stats`

For the demo and for watching the spend cap.

```json
{
  "pitches_total": 12,
  "image_calls_used": 9,
  "image_calls_remaining": 31,
  "avg_elapsed_ms": 19105
}
```

---

## Notes

- CORS is wide open. Hackathon, one day, local network.
- No auth.
- `web/` is served as static files, so `index.html` and `gallery.html` call the API on the
  same origin. No proxy configuration needed.
- Slug format: `slugify(brand_name)` + `-` + 5 random lowercase alphanumeric characters.
  Two identical brand names must never collide.
