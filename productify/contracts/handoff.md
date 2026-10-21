# Handoff contract — Station 1 → Station 2 — FROZEN

Agreed at minute 30. This is the only interface between the two laptops. Any change must be
announced out loud to both stations and made by one person only.

Station 1 produces content. Station 2 turns it into a page. Nothing else crosses the line.

---

## Face 1 — in process (what runs in production)

Station 2 implements exactly this. Station 1 calls it. The signature is frozen.

```python
# app/render/__init__.py — implemented by Station 2
def render_pitch(
    pack: ContentPack,            # already validated by Station 1
    photo_bytes: bytes,           # the original upload, any size
    logo_bytes: bytes | None,     # None on the first render; real PNG on the re-render
) -> str:                         # a complete, self-contained HTML document
```

**Guarantees Station 1 makes about `pack`:**

- It has passed the `ContentPack` Pydantic model.
- `features` has **exactly 3** items, `pricing` **exactly 3**, `testimonials` **exactly 2**.
- **Exactly one** pricing tier has `highlighted: true`.
- Every value in `theme.palette` matches `^#[0-9a-fA-F]{6}$`.
- `theme.font_pair`, `theme.radius` and `theme.mood` are values from the schema enums.
- Every `icon_hint` is a value from the schema enum.

Station 2 may rely on all of the above and does **not** need defensive checks for them.

**What Station 2 must still handle defensively:**

- Any string may be **long** — a 90-character brand name, a 300-character tagline. Nothing
  may overflow or clip.
- Any string may be **empty**.
- Any string may contain `<`, `>`, `&` or quotes. Jinja2 `autoescape` stays on.
- `logo_bytes` is `None` on the first render. The page must look finished anyway —
  an inline SVG monogram from the brand initials, not a broken image icon.
- The palette may be valid but **ugly or low-contrast**. `ensure_contrast()` is Station 2's
  responsibility, not Station 1's.

**Guarantees Station 2 makes about the return value:**

- A complete HTML document, `<!DOCTYPE html>` through `</html>`.
- **Zero external requests.** No CDN, no stylesheet link, no Google Fonts, no remote image.
  Images are `data:` URIs. It renders with the network off.
- Under 3 MB.
- Deterministic: the same inputs produce the same output.

Station 1 calls `render_pitch` **twice** per pitch — once with `logo_bytes=None` to publish
immediately, then again from the background task once the logo exists, overwriting
`index.html`. Station 2's implementation must be safe to call repeatedly.

---

## Face 2 — on disk (how the two laptops actually exchange work)

This is the face that lets Station 2 build all day without ever running Station 1's code.

### Live pitches — written by Station 1

```
out/pitches/{slug}/
├── pitch.json     # {"pack": {...}, "tone": "vc", "created_at": "...", "has_logo": false}
├── photo.jpg      # the upload, resized to max 1200px long edge
├── logo.png       # 1024x1024; ABSENT until the background task finishes
├── index.html     # produced by Station 2's render_pitch
└── meta.json      # the PitchSummary from contracts/api.md
```

`out/` is gitignored. This is runtime output, not shared work.

### Bundles — the transfer unit between laptops

```
fixtures/bundles/{name}/
├── bundle.json    # same shape as pitch.json above
├── photo.jpg
└── logo.png       # optional
```

`fixtures/bundles/` is **committed** — deliberately. `bundle.json` is ~4 KB, the photo
~200 KB, the logo ~80 KB. All four tones come to well under 1 MB. For a one-day project
this is the simplest transfer mechanism that exists, and it means every bundle Station 2
develops against is a real model output, not a guess.

**Station 1 exports:**
```bash
python -m eval.export_bundle --photo fixtures/photos/stapler.jpg --tones all --name-prefix stapler
git add fixtures/bundles && git commit -m "add 4 real bundles, one per tone" && git push origin feat/pipeline
```

**Station 2 consumes:**
```bash
git fetch && git checkout origin/feat/pipeline -- fixtures/bundles
python -m app.render.preview fixtures/bundles/stapler-vc --open
python -m app.render.preview --all      # the four-tone comparison
```

Station 1 owes Station 2 **four bundles, one per tone, by hour 1:45.** That is the hardest
deadline of the day — until it lands, Station 2 is working against a hand-written example.

### `bundle.json` / `pitch.json` shape

```json
{
  "pack": { "...a full ContentPack per contracts/content_pack.schema.json..." },
  "tone": "vc",
  "object": "stapler",
  "created_at": "2026-08-11T09:41:02Z",
  "has_logo": false
}
```

Station 1 validates `pack` through the Pydantic model **before writing**. A malformed
bundle must never reach Station 2 — if it does, Station 2 reports it rather than working
around it.

---

## Who owns what, restated

| | Station 1 | Station 2 |
|---|---|---|
| **Owns** | `app/main.py`, `app/config.py`, `app/models.py`, `app/storage.py`, `app/pipeline/*`, `eval/*`, `fixtures/*` | `app/render/*`, `web/*`, `DEMO.md` |
| **API calls** | all three model calls | none |
| **Has the OpenAI key** | yes | no — runs `MOCK=1` all day |
| **Runs the server at demo** | yes | merges into Station 1's laptop at freeze |

`app/main.py` mounts `web/` as StaticFiles from the scaffold onwards, so Station 2 never
needs to open it. If Station 2 believes a change to `app/main.py` is required, that is a
conversation, not a commit.

---

## Changes that require talking, not committing

- A new field in `ContentPack` → both stations, out loud, then Station 1 edits the schema.
- A new parameter to `render_pitch` (for example the QR code stretch goal) → announce, then
  Station 1 puts it **inside `pack`** rather than extending the signature, if at all possible.
- A new enum value in `font_pair`, `mood`, `radius` or `icon_hint` → Station 2 proposes,
  Station 1 edits the schema, both pull.
- Anything in `contracts/api.md` → announce; Station 2 depends on every field of it.
