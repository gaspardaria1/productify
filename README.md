# Productify

A photo of any object goes in; a self-contained HTML pitch page for an invented company
comes out. See `CLAUDE.md` for context and `contracts/` for the frozen interfaces.

## Run — Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

That is **mock mode**: no API calls, no key needed, no spend. `MOCK` defaults to `True`.

Then open http://localhost:8000 — it redirects to the capture screen. The gallery is at
http://localhost:8000/web/gallery.html and the health check at
http://localhost:8000/health, which tells you which mode you are in.

## Run — macOS / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Real API calls

Two things are required, and missing either one silently leaves you in mock mode:

1. A key in `.env` — copy `.env.example` to `.env` and paste it in an editor. Never paste a
   key into a shell command or a chat window; both get logged.
2. `MOCK=0`, either in `.env` or in the environment.

```powershell
$env:MOCK=0; uvicorn app.main:app --reload    # PowerShell
```
```bash
MOCK=0 uvicorn app.main:app --reload          # bash
```

Confirm with `GET /health` → `{"ok": true, "mock": false}`. `.env` is gitignored; verify
with `git check-ignore -v .env`.

## From a phone

Uvicorn binds to `127.0.0.1` by default, which a phone cannot reach. Bind to all interfaces
and browse to the laptop's LAN IP on the same WiFi:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0
```

Find the IP with `ipconfig` and use the one on the WiFi adapter — a machine with VirtualBox
or Docker also shows a `192.168.56.x` host-only address that the phone cannot reach. Windows
Firewall will likely prompt on the first bind; it has to be allowed on the private network,
and that has to be tested before the demo, not during it.
