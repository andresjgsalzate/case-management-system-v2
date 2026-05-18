"""Catalog of supported alert-report block types + Pydantic validation.

A template's ``blocks`` JSON column is an ordered list of
``{"type": <block_type>, "params": <dict>}`` entries. Each block type maps
to a Pydantic schema that validates its params before persistence — the
renderer (Task 6) then trusts the structure and skips defensive checks.

The 14 block types match spec §3.6. Blocks with no required params reuse
``BaseModel`` (accepts arbitrary keys silently). Required-param schemas
inherit from ``StrictBlockParams`` which forbids extras so typos in
admin-supplied JSON surface as validation errors instead of silent drops.
"""
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from backend.src.core.exceptions import ValidationError


class StrictBlockParams(BaseModel):
    """Base for blocks with required params. ``extra='forbid'`` rejects typos."""
    model_config = ConfigDict(extra="forbid")


class AlertMetadataParams(BaseModel):
    show_repeticiones: bool = True
    show_tlp: bool = True


class PriorityCalculationParams(BaseModel):
    show_formula_name: bool = True
    show_inputs_table: bool = True


class TextBlockParams(StrictBlockParams):
    title: str | None = None
    content_template: str
    show_title: bool = True
    use_markdown: bool = False


class TriageAnalysisParams(BaseModel):
    show_taxonomy_chain: bool = True


class EvidenceGridParams(BaseModel):
    include_forensic_hunts: bool = True
    include_user_attachments: bool = True
    include_iocs: bool = False


class ForensicArtifactsListParams(BaseModel):
    show_chain_of_custody: bool = True


class BehaviorRelationParams(BaseModel):
    """Human-authored description of attacker behavior — no required params."""


class RecommendationsParams(BaseModel):
    default_recommendations: list[str] = Field(default_factory=list)
    show_default_if_empty: bool = True


class MitreTechniquesParams(BaseModel):
    include_table: bool = True


class IocsTableParams(BaseModel):
    columns: list[str] = Field(
        default_factory=lambda: ["type", "value", "source"],
    )


class SignerEntry(BaseModel):
    role: str
    label: str


class SignatureParams(StrictBlockParams):
    signers: list[SignerEntry]


class PageBreakParams(BaseModel):
    """No params — purely a layout marker."""


class SpacerParams(BaseModel):
    height_px: int = 20


class ImageParams(StrictBlockParams):
    attachment_id: str
    max_width_pct: int = 100
    caption: str | None = None


BLOCK_SCHEMAS: dict[str, type[BaseModel]] = {
    "alert_metadata": AlertMetadataParams,
    "priority_calculation": PriorityCalculationParams,
    "text": TextBlockParams,
    "triage_analysis": TriageAnalysisParams,
    "evidence_grid": EvidenceGridParams,
    "forensic_artifacts_list": ForensicArtifactsListParams,
    "behavior_relation": BehaviorRelationParams,
    "recommendations": RecommendationsParams,
    "mitre_techniques": MitreTechniquesParams,
    "iocs_table": IocsTableParams,
    "signature": SignatureParams,
    "page_break": PageBreakParams,
    "spacer": SpacerParams,
    "image": ImageParams,
}


def validate_blocks(blocks: list[dict]) -> None:
    """Validate a template's ``blocks`` array.

    Raises ``ValidationError`` (project's exception type, not Pydantic's)
    with the position of the offending block + the underlying parse error.
    """
    for i, block in enumerate(blocks):
        btype = block.get("type")
        if btype not in BLOCK_SCHEMAS:
            raise ValidationError(
                f"Block {i}: type '{btype}' unknown. "
                f"Valid types: {sorted(BLOCK_SCHEMAS)}"
            )
        schema = BLOCK_SCHEMAS[btype]
        try:
            schema(**block.get("params", {}))
        except PydanticValidationError as e:
            raise ValidationError(f"Block {i} ({btype}): {e}") from e
