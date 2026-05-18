"""Block-based HTML rendering for alert reports.

A template's ``blocks`` array is rendered to HTML one block at a time,
then wrapped in ``base_document.html``. Block handlers live in this
module; the per-block HTML lives in ``templates/blocks/*.html``.

Security model:
- The ``BlockRenderer.env`` is a ``SandboxedEnvironment`` — user-supplied
  Jinja2 fragments (the ``text`` block's ``content_template``) cannot
  access attributes like ``__class__``, ``__subclasses__``, or call
  arbitrary builtins. Attempts raise ``jinja2.SecurityError``.
- When the ``text`` block has ``use_markdown=True``, the rendered Markdown
  is run through ``bleach.clean`` with a tag/attr allowlist — ``<script>``,
  ``<iframe>``, inline event handlers etc. are stripped.
- All other block templates use ``autoescape=True`` (HTML escaping on by
  default for ``html/xhtml`` files).
"""
import re
from html import escape as html_escape
from pathlib import Path
from typing import Any

import bleach
import markdown as md_lib
from jinja2 import FileSystemLoader, select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from backend.src.modules.alert_reports.application.blocks_catalog import (
    BLOCK_SCHEMAS,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Pre-strip these tags + their contents before passing to bleach. bleach's
# strip=True removes the tag but leaves the text — for <script>alert(1)</script>
# that means "alert(1)" survives, which would let user templates leak
# script bodies into the rendered HTML.
DANGEROUS_BLOCK_RE = re.compile(
    r"<(script|style|iframe|object|embed|svg)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

MARKDOWN_ALLOWED_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li",
    "strong", "em", "code", "pre",
    "a", "table", "thead", "tbody", "tr", "td", "th",
    "blockquote", "hr", "br",
]
MARKDOWN_ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "th": ["scope"],
}


class BlockRenderer:
    def __init__(self) -> None:
        self.env = SandboxedEnvironment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xhtml"]),
        )
        self.handlers = {
            "alert_metadata": self._render_alert_metadata,
            "priority_calculation": self._render_priority_calculation,
            "text": self._render_text,
            "triage_analysis": self._render_triage,
            "evidence_grid": self._render_evidence_grid,
            "forensic_artifacts_list": self._render_forensic_list,
            "behavior_relation": self._render_behavior,
            "recommendations": self._render_recommendations,
            "mitre_techniques": self._render_mitre,
            "iocs_table": self._render_iocs,
            "signature": self._render_signature,
            "page_break": lambda b, s: '<div class="page-break"></div>',
            "spacer": self._render_spacer,
            "image": self._render_image,
        }

    def render(
        self,
        *,
        blocks: list[dict[str, Any]],
        snapshot: dict[str, Any],
        header_config: dict[str, Any],
        footer_config: dict[str, Any],
    ) -> str:
        body_parts: list[str] = []
        for block in blocks:
            btype = block.get("type", "")
            handler = self.handlers.get(btype)
            if not handler:
                safe = html_escape(str(btype))
                body_parts.append(
                    f'<div class="block-error">Unknown block: {safe}</div>'
                )
                continue
            html = handler(block, snapshot)
            body_parts.append(
                f'<div class="block block-{html_escape(btype)}">{html}</div>'
            )

        document_template = self.env.get_template("base_document.html")
        return document_template.render(
            header_config=header_config,
            footer_config=footer_config,
            body_html="\n".join(body_parts),
            snapshot=snapshot,
        )

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_params(block: dict[str, Any]) -> dict[str, Any]:
        """Pass raw params through the block's Pydantic schema.

        Returns a dict where every optional param has its declared default
        filled in. Templates can then safely use ``params.show_tlp``
        without checking for missing keys.
        """
        btype = block.get("type", "")
        raw = block.get("params", {}) or {}
        schema = BLOCK_SCHEMAS.get(btype)
        if schema is None:
            return raw
        try:
            return schema(**raw).model_dump()
        except Exception:
            return raw

    # ── handlers ─────────────────────────────────────────────────────────

    def _render_alert_metadata(self, block, snapshot):
        tpl = self.env.get_template("blocks/alert_metadata.html")
        return tpl.render(
            case=snapshot.get("case", {}),
            params=self._resolve_params(block),
        )

    def _render_priority_calculation(self, block, snapshot):
        tpl = self.env.get_template("blocks/priority_calculation.html")
        return tpl.render(
            calc=snapshot.get("priority_calculation"),
            params=self._resolve_params(block),
        )

    def _render_text(self, block, snapshot):
        params = block.get("params", {})
        content_tpl = self.env.from_string(
            params.get("content_template", "")
        )
        rendered = content_tpl.render(
            case=snapshot.get("case", {}),
            forensic_hunts=snapshot.get("forensic_hunts", []),
            recommendations=snapshot.get("recommendations") or "",
            notes_summary=snapshot.get("notes_summary", ""),
        )
        if params.get("use_markdown"):
            # Strip <script>, <style>, etc. INCLUDING their text content
            # before bleach. bleach.clean(strip=True) would only remove the
            # tags but leave the body text, which is unsafe.
            pre_cleaned = DANGEROUS_BLOCK_RE.sub("", rendered)
            html = md_lib.markdown(
                pre_cleaned, extensions=["tables", "fenced_code"]
            )
            rendered = bleach.clean(
                html,
                tags=MARKDOWN_ALLOWED_TAGS,
                attributes=MARKDOWN_ALLOWED_ATTRS,
                strip=True,
            )
        title = params.get("title")
        if title and params.get("show_title", True):
            return f"<h2>{html_escape(title)}</h2>{rendered}"
        return rendered

    def _render_triage(self, block, snapshot):
        tpl = self.env.get_template("blocks/triage_analysis.html")
        return tpl.render(
            case=snapshot.get("case", {}),
            notes_summary=snapshot.get("notes_summary", ""),
            params=block.get("params", {}),
        )

    def _render_evidence_grid(self, block, snapshot):
        params = block.get("params", {})
        tpl = self.env.get_template("blocks/evidence_grid.html")
        return tpl.render(
            forensic_hunts=(
                snapshot.get("forensic_hunts", [])
                if params.get("include_forensic_hunts", True)
                else []
            ),
            attachments=(
                snapshot.get("evidence_attachments", [])
                if params.get("include_user_attachments", True)
                else []
            ),
            iocs=(
                snapshot.get("iocs", [])
                if params.get("include_iocs", False)
                else []
            ),
            params=params,
        )

    def _render_forensic_list(self, block, snapshot):
        tpl = self.env.get_template("blocks/forensic_artifacts_list.html")
        return tpl.render(
            hunts=snapshot.get("forensic_hunts", []),
            params=block.get("params", {}),
        )

    def _render_behavior(self, block, snapshot):
        tpl = self.env.get_template("blocks/behavior_relation.html")
        return tpl.render(
            text=snapshot.get("behavior_relation") or "",
            params=block.get("params", {}),
        )

    def _render_recommendations(self, block, snapshot):
        params = block.get("params", {})
        snapshot_recs = snapshot.get("recommendations")
        defaults = params.get("default_recommendations", []) or []
        if snapshot_recs:
            items = (
                snapshot_recs
                if isinstance(snapshot_recs, list)
                else [snapshot_recs]
            )
        elif params.get("show_default_if_empty", True):
            items = defaults
        else:
            items = []
        tpl = self.env.get_template("blocks/recommendations.html")
        return tpl.render(items=items)

    def _render_mitre(self, block, snapshot):
        tpl = self.env.get_template("blocks/mitre_techniques.html")
        return tpl.render(
            techniques=snapshot.get("mitre_techniques", []),
            params=block.get("params", {}),
        )

    def _render_iocs(self, block, snapshot):
        params = block.get("params", {})
        columns = params.get("columns") or ["type", "value", "source"]
        tpl = self.env.get_template("blocks/iocs_table.html")
        return tpl.render(
            iocs=snapshot.get("iocs", []),
            columns=columns,
        )

    def _render_signature(self, block, snapshot):
        tpl = self.env.get_template("blocks/signature.html")
        return tpl.render(
            signers=block.get("params", {}).get("signers", []),
        )

    def _render_spacer(self, block, snapshot):
        h = int(block.get("params", {}).get("height_px", 20))
        return f'<div class="spacer" style="height: {h}px"></div>'

    def _render_image(self, block, snapshot):
        tpl = self.env.get_template("blocks/image.html")
        return tpl.render(
            params=block.get("params", {}),
        )
