"""
Step 4: PUBLISH. Owned by Station 2. Signature is frozen — see
contracts/handoff.md before changing it.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import ContentPack
from app.render import package, theme

_ENV = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent)),
    autoescape=select_autoescape(["html"]),
)
_ENV.globals["icon_svg"] = package.icon_svg
_TEMPLATE = _ENV.get_template("template.html")


def render_pitch(pack: ContentPack, photo_bytes: bytes, logo_bytes: bytes | None) -> str:
    css_vars = theme.build_css_vars(pack.theme)
    photo_data_uri = package.embed_photo(photo_bytes) if photo_bytes else None
    logo_markup = package.embed_logo_markup(
        pack.brand.name, pack.theme.palette.accent, css_vars["--pf-button-label"], logo_bytes
    )
    favicon_data_uri = package.monogram_data_uri(
        pack.brand.name, pack.theme.palette.accent, css_vars["--pf-button-label"]
    )

    html = _TEMPLATE.render(
        pack=pack,
        css_vars=css_vars,
        photo_data_uri=photo_data_uri,
        logo_markup=logo_markup,
        favicon_data_uri=favicon_data_uri,
    )

    package.assert_self_contained(html)
    return html
