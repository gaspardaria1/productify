"""
CLI for iterating on the render engine with no backend running — the
Station 2 development loop for the whole day.

  python -m app.render.preview fixtures/bundles/stapler-vc --open
  python -m app.render.preview fixtures/stapler.vc.json --open
  python -m app.render.preview --all
  python -m app.render.preview fixtures/bundles/stapler-vc --watch
"""

import argparse
import json
import sys
import time
import webbrowser
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw
from pydantic import ValidationError

from app.models import ContentPack
from app.render import render_pitch

PREVIEW_DIR = Path("preview")
PLACEHOLDER_SIZE = (800, 600)


def _placeholder_photo() -> bytes:
    img = Image.new("RGB", PLACEHOLDER_SIZE, "#333333")
    draw = ImageDraw.Draw(img)
    draw.text((24, 24), "no photo in fixture — preview placeholder", fill="#EEEEEE")
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


class BadFixture(Exception):
    """A fixture or bundle that cannot be rendered. Raised rather than exiting
    so --all can skip one bad file and still produce the comparison index."""


def _load_bundle_dir(path: Path) -> tuple[ContentPack, bytes, bytes | None, str]:
    bundle_path = path / "bundle.json"
    if not bundle_path.exists():
        raise BadFixture(f"{path} has no bundle.json — not a valid bundle")
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BadFixture(f"{bundle_path} is not valid JSON — {exc}") from exc
    try:
        pack = ContentPack.model_validate(data["pack"])
    except (KeyError, TypeError, ValidationError) as exc:
        raise BadFixture(f"{path} is not a valid bundle — {exc}") from exc
    photo_path = path / "photo.jpg"
    photo_bytes = photo_path.read_bytes() if photo_path.exists() else _placeholder_photo()
    logo_path = path / "logo.png"
    logo_bytes = logo_path.read_bytes() if logo_path.exists() else None
    return pack, photo_bytes, logo_bytes, path.name


def _load_bare_json(path: Path) -> tuple[ContentPack, bytes, bytes | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BadFixture(f"{path} is not valid JSON — {exc}") from exc
    # Accept a bundle.json that was pointed at directly, not just a bare pack.
    if isinstance(data, dict) and "pack" in data:
        data = data["pack"]
    try:
        pack = ContentPack.model_validate(data)
    except (TypeError, ValidationError) as exc:
        raise BadFixture(f"{path} is not a valid ContentPack — {exc}") from exc
    return pack, _placeholder_photo(), None, path.stem


def _load(path: Path) -> tuple[ContentPack, bytes, bytes | None, str]:
    return _load_bundle_dir(path) if path.is_dir() else _load_bare_json(path)


def _render_one(path: Path) -> Path:
    pack, photo_bytes, logo_bytes, name = _load(path)
    html = render_pitch(pack, photo_bytes, logo_bytes)
    PREVIEW_DIR.mkdir(exist_ok=True)
    out_path = PREVIEW_DIR / f"{name}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"rendered {path} -> {out_path} ({len(html) / 1024:.0f} KB)")
    return out_path


def _discover_all() -> list[Path]:
    targets: list[Path] = []
    bundles_dir = Path("fixtures/bundles")
    if bundles_dir.exists():
        targets.extend(sorted(p for p in bundles_dir.iterdir() if p.is_dir() and (p / "bundle.json").exists()))
    fixtures_dir = Path("fixtures")
    if fixtures_dir.exists():
        targets.extend(sorted(fixtures_dir.glob("*.json")))
    return targets


def _write_index(rendered: list[Path]) -> Path:
    items = "\n".join(
        f'<li><a href="{escape(p.name, quote=True)}" target="preview">{escape(p.stem)}</a></li>'
        for p in rendered
    )
    index_path = PREVIEW_DIR / "index.html"
    index_path.write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Productify previews</title>"
        "<style>body{font-family:sans-serif;margin:0;display:flex;height:100vh}"
        "nav{width:220px;overflow:auto;padding:16px;border-right:1px solid #ccc}"
        "iframe{flex:1;border:none}</style></head><body>"
        f"<nav><h3>Previews</h3><ul>{items}</ul></nav>"
        '<iframe name="preview"></iframe></body></html>',
        encoding="utf-8",
    )
    return index_path


def _watch_targets(path: Path) -> list[Path]:
    """The fixture plus the render sources. Watching only the fixture would miss
    the files this loop actually exists to iterate on — the template and theme.
    """
    render_dir = Path(__file__).parent
    targets = [path / "bundle.json" if path.is_dir() else path]
    targets += [render_dir / name for name in ("template.html", "theme.py", "package.py", "__init__.py")]
    return [t for t in targets if t.exists()]


def _fingerprint(paths: list[Path]) -> dict[Path, float]:
    return {p: p.stat().st_mtime for p in paths if p.exists()}


def _watch(path: Path) -> None:
    watched = _watch_targets(path)
    print("watching for changes (Ctrl+C to stop):")
    for w in watched:
        print(f"  {w}")
    _render_one(path)
    last = _fingerprint(watched)
    try:
        while True:
            time.sleep(1)
            current = _fingerprint(watched)
            if current != last:
                changed = [p.name for p in current if last.get(p) != current[p]]
                last = current
                print(f"changed: {', '.join(changed)}")
                try:
                    _reload_render()
                    _render_one(path)
                except BadFixture as exc:
                    print(f"error: {exc}", file=sys.stderr)
                except Exception as exc:  # keep the loop alive across a broken edit
                    print(f"render failed: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        pass


def _reload_render() -> None:
    """Re-import the render package so template/theme edits take effect without
    restarting the watcher."""
    import importlib

    from app.render import package as package_mod
    from app.render import theme as theme_mod

    importlib.reload(theme_mod)
    importlib.reload(package_mod)
    import app.render

    importlib.reload(app.render)
    globals()["render_pitch"] = app.render.render_pitch


def main() -> None:
    parser = argparse.ArgumentParser(description="Render ContentPack fixtures/bundles with no backend.")
    parser.add_argument("path", nargs="?", help="a bundle directory or a bare ContentPack JSON file")
    parser.add_argument("--all", action="store_true", help="render every bundle and fixture into preview/")
    parser.add_argument("--open", action="store_true", help="open the result in a browser")
    parser.add_argument("--watch", action="store_true", help="re-render on file change")
    args = parser.parse_args()

    if args.all:
        targets = _discover_all()
        if not targets:
            print("no bundles or fixtures found under fixtures/", file=sys.stderr)
            sys.exit(1)
        # Skip anything unrenderable rather than aborting: fixtures/ belongs to
        # Station 1 and one unrelated .json must not cost us the whole
        # four-tone comparison index.
        rendered: list[Path] = []
        skipped: list[str] = []
        for t in targets:
            try:
                rendered.append(_render_one(t))
            except BadFixture as exc:
                skipped.append(str(exc))
        for message in skipped:
            print(f"skipped: {message}", file=sys.stderr)
        if not rendered:
            print("nothing could be rendered", file=sys.stderr)
            sys.exit(1)
        index_path = _write_index(rendered)
        print(f"wrote {index_path} linking {len(rendered)} previews" + (f", skipped {len(skipped)}" if skipped else ""))
        if args.open:
            webbrowser.open(index_path.resolve().as_uri())
        return

    if not args.path:
        parser.error("path is required unless --all is given")

    path = Path(args.path)
    if not path.exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    # A single explicit target still fails loudly — if a bundle Station 1 handed
    # over is malformed I want to know instantly and tell them, not debug my CSS.
    try:
        if args.watch:
            _watch(path)
            return
        out_path = _render_one(path)
    except BadFixture as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.open:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
