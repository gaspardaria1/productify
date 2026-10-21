# Productify — context for Claude Code

One-day hackathon build. Four people working in parallel on separate branches.
**Read this file at the start of every session.**

## What the app does

A photo of any object goes in; a complete, self-contained HTML pitch page for an invented
company comes out, in under a minute. Every page is saved and listed in a gallery.

Pipeline, four chained calls:
1. **Look** — vision call → `VisionResult` (object, quirks, material, condition)
2. **Invent** — one Structured Outputs call → `ContentPack` (all copy + a theme object)
3. **Brand** — `gpt-image-1` → logo PNG, generated in the background
4. **Publish** — template + theme → one self-contained HTML file at `/pitch/{slug}`

## Stack

FastAPI + Jinja2 + Pillow on the backend. Plain HTML/CSS/vanilla JS on the frontend —
**no framework, no build step, no npm.** Files on disk under `out/pitches/{slug}/`.
No database. OpenAI Python SDK. Python 3.11+.

## The frozen contracts

`contracts/content_pack.schema.json`, `contracts/api.md` and `contracts/handoff.md` are
**frozen**. Never modify
them. If a task seems to require a change to any of them, stop and say so instead of editing.

Same for this function signature — the seam between the two stations:
```python
# app/render/__init__.py — implemented by Station 2, called by Station 1
def render_pitch(pack: ContentPack, photo_bytes: bytes, logo_bytes: bytes | None) -> str
```

`render_pitch` is called **twice** per pitch: once with `logo_bytes=None` to publish
immediately, then again from the background task once the logo exists. It must be safe to
call repeatedly.

## File ownership — two stations, two branches

Four people, **two laptops**. Two branches. Two lanes of files with zero overlap.

| Station | Branch | Owns (only these files may be edited) |
|---|---|---|
| **S1** Perception & Generation | `feat/pipeline` | `app/main.py`, `app/config.py`, `app/models.py`, `app/storage.py`, `app/pipeline/*`, `eval/*`, `fixtures/*`, `requirements.txt` |
| **S2** Presentation | `feat/render` | `app/render/*`, `web/*`, `DEMO.md` |

S1 owns all three model calls. S2 owns the render step and the whole UI.

`app/main.py` mounts `web/` as StaticFiles from the scaffold onwards, so **S2 never needs to
open it.** If a task in S2 seems to require editing `app/main.py`, or a task in S1 seems to
require editing `app/render/*`, **stop and describe the change instead of making it.**

The seam between the stations is defined in `contracts/handoff.md`. Read it before any task
that touches either side of it.

## Hard rules

- **Never read, print, log, or hardcode `OPENAI_API_KEY`.** It comes from `.env`, which is
  gitignored. Do not create files that contain it. Do not echo it in commands.
- **The OpenAI key lives only on Station 1's laptop.** Station 2 runs `MOCK=1` all day and
  never needs it. Every pipeline stage keeps a minimal mock branch returning fixture data —
  three lines, not a mock framework.
- **`fixtures/bundles/` is committed on purpose** (note the `!fixtures/bundles/` negation in
  `.gitignore`). It is how real model output crosses between the two laptops. See
  `contracts/handoff.md`.
- **One `gpt-image-1` call per pitch, maximum.** Check `config.can_call_image()` before
  every image call. There is a shared spend cap.
- **The image call must never block the response.** The page renders and returns with an
  inline SVG monogram placeholder; the real logo is swapped in by a background task.
- **Jinja2 autoescape stays on.** Every string in the page came from a language model.
- **The output page is self-contained.** No CDN, no external stylesheet, no Google Fonts
  link, no remote image. Images are base64 data URIs. It must render with the network off.
- **The demo path never hard-fails.** A degraded page beats a stack trace. Vision failure
  falls back to a generic result; palette validation failure falls back to a default theme.

## Structured Outputs — strict mode limitations

`pattern`, `format`, `minItems`, `maxItems`, `minLength`, `minimum` and `maximum` are
**not supported** in strict mode. `enum` is. So:

- Counts (exactly 3 features, 3 pricing tiers, 2 testimonials) are requested in the prompt
  and **enforced in Python** after parsing — truncate if too many, pad if too few.
- Hex colours are validated in Python against `^#[0-9a-fA-F]{6}$`. If any palette value
  fails, replace the **entire** palette with the default — partial palettes look broken.
- `font_pair` is an `enum` in the schema, so it is safe; still fall back to the first
  value if something unexpected arrives.
- Every object needs `additionalProperties: false` and every property listed in `required`.

## Conventions

- Async FastAPI handlers. `httpx`/SDK async clients, never blocking calls in a handler.
- Pydantic v2 models in `app/models.py` are the single source of truth in Python; the JSON
  schema in `contracts/` is the source of truth for the API call. Keep them in agreement.
- Type hints on public functions. No docstring ceremony — this is a one-day build.
- No tests unless explicitly asked. Log timings instead: we narrate them during the demo.
- Commit messages: imperative, lowercase, English. `add vision call`, `fix palette contrast`.
- Log elapsed time per pipeline stage. Never log base64 blobs or keys.

## Commands

Both laptops are Windows, so PowerShell is the default shell. `VAR=1 cmd` is bash
syntax and fails in PowerShell with `The term 'MOCK=1' is not recognized`.

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload                 # mock mode — MOCK defaults to True
$env:MOCK=0; uvicorn app.main:app --reload    # REAL API calls; needs a key in .env
uvicorn app.main:app --reload --host 0.0.0.0  # reachable from a phone on the same WiFi
python -m app.render.preview fixtures/stapler.vc.json --open   # template iteration
python -m app.render.preview --all            # compare all four tones
python -m eval.run_batch --photos fixtures/photos --tones all   # quality report
```

Bash/macOS equivalent for the two that differ:

```bash
MOCK=0 uvicorn app.main:app --reload
uvicorn app.main:app --reload --host 0.0.0.0
```

**`MOCK` defaults to `True`** (`app/config.py`), so plain `uvicorn app.main:app` runs
mocked and makes **no** API calls — that is the safe default, not the real one. Real calls
need `MOCK=0` **and** a key in `.env`. Check which mode you are in at `GET /health`, which
returns `{"ok": true, "mock": true|false}`, and at startup, which logs `mock=...`.

## Scope discipline

Must-haves, in order, before anything else:
1. Photo in → pitch page out, under 60 seconds
2. Tone selector: `vc`, `luxury`, `infomercial`, `kickstarter` — visibly different results
3. Gallery: every page listed, openable, each downloadable as a single `.html`

Stretch goals (QR code, VC verdict, TTS, YOLO mode) are only started once all three
must-haves are green. A complete working demo path beats five half-finished features.
When a task is ambiguous, choose the option that makes the demo more reliable.
