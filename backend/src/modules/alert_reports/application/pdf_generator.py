"""WeasyPrint-based HTML → PDF rendering.

Layout shape:
- ``@page`` rules drive the **running** header/footer — they appear on
  every page automatically and are NOT part of the body HTML. This is
  WeasyPrint's CSS-paged-media support (CSS Paged Media Module Level 3).
- The TLP banner and a "Página N de M" counter use ``content:`` strings in
  ``@top-right`` / ``@bottom-center`` margin boxes. ``counter(pages)``
  gives the total page count for the "de N" half.
- ``css_overrides`` (per-template admin CSS) is appended LAST so it can
  override base styles without monkey-patching default.css.

WeasyPrint's ``write_pdf()`` is synchronous and CPU-bound (rendering
text + layout); ``html_to_pdf`` wraps it in ``asyncio.to_thread`` so the
FastAPI event loop is not blocked.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import weasyprint

logger = logging.getLogger(__name__)

CSS_DIR = Path(__file__).resolve().parent.parent / "templates"
DEFAULT_CSS_PATH = CSS_DIR / "default.css"

TLP_COLORS = {
    "RED": "#FF2B2B",
    "AMBER": "#FFC000",
    "GREEN": "#33A02C",
    "WHITE": "#000000",
}


async def html_to_pdf(
    *,
    html: str,
    header_config: dict,
    footer_config: dict,
    snapshot: dict,
    css_overrides: str | None = None,
) -> bytes:
    """Render ``html`` to a PDF buffer.

    ``header_config`` and ``footer_config`` drive the @page margin boxes
    (title, TLP banner, page numbers, footer text, generation timestamp).
    ``snapshot`` is the same dict produced by ``snapshot_builder`` and is
    only consulted for ``snapshot['case']['tlp']`` in this generator —
    block-level interpolation already happened in ``block_renderer``.
    """
    stylesheets: list[weasyprint.CSS] = []
    if DEFAULT_CSS_PATH.exists():
        stylesheets.append(weasyprint.CSS(filename=str(DEFAULT_CSS_PATH)))

    page_css = _build_page_css(header_config, footer_config, snapshot)
    stylesheets.append(weasyprint.CSS(string=page_css))

    if css_overrides:
        stylesheets.append(weasyprint.CSS(string=css_overrides))

    def _render_sync() -> bytes:
        # `base_url` lets relative paths in the HTML (e.g. images) resolve
        # against the templates folder. Remote URL fetching stays disabled
        # by default (WeasyPrint 60+).
        doc = weasyprint.HTML(string=html, base_url=str(CSS_DIR))
        return doc.write_pdf(stylesheets=stylesheets)

    return await asyncio.to_thread(_render_sync)


def _build_page_css(
    header_config: dict, footer_config: dict, snapshot: dict
) -> str:
    tlp = (snapshot.get("case", {}).get("tlp") or "WHITE").upper()
    title = _escape_css(header_config.get("title_template", ""))
    footer_text = _escape_css(footer_config.get("footer_text", ""))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tlp_color = TLP_COLORS.get(tlp, "#000000")

    parts = [
        "@page {",
        "  size: A4;",
        "  margin: 25mm 20mm;",
    ]
    if title:
        parts.append(
            f'  @top-center {{ content: "{title}"; '
            f'font-size: 10pt; font-weight: bold; }}'
        )
    parts.append(
        f'  @top-right {{ content: "TLP: {tlp}"; '
        f'color: {tlp_color}; font-weight: bold; font-size: 10pt; }}'
    )
    if footer_config.get("show_page_numbers", True):
        parts.append(
            '  @bottom-center { content: "Página " counter(page) '
            '" de " counter(pages); font-size: 9pt; }'
        )
    if footer_text:
        parts.append(
            f'  @bottom-left {{ content: "{footer_text}"; '
            f'font-size: 8pt; color: #666; }}'
        )
    if footer_config.get("show_generation_timestamp", True):
        parts.append(
            f'  @bottom-right {{ content: "Generado: {timestamp}"; '
            f'font-size: 8pt; color: #666; }}'
        )
    parts.append("}")
    parts.append(".page-break { page-break-after: always; }")
    return "\n".join(parts)


def _escape_css(value: str) -> str:
    """Escape characters that would break a CSS string literal.

    Admin-supplied ``title_template`` / ``footer_text`` could contain
    double quotes or backslashes — both would terminate the CSS string or
    introduce escape sequences. Strip aggressively rather than try to
    encode every CSS-special char.
    """
    return value.replace("\\", "").replace('"', "'")
