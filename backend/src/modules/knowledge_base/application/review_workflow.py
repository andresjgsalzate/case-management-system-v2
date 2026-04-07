from backend.src.core.exceptions import BusinessRuleError


class WorkflowError(BusinessRuleError):
    """
    Error de transición inválida en el workflow de aprobación KB.
    Extiende BusinessRuleError para que el handler HTTP lo capture
    automáticamente como HTTP 422.
    """
    pass


# Grafo de transiciones válidas: { from_status: [to_status, ...] }
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":     ["in_review"],
    "in_review": ["approved", "rejected"],
    "approved":  ["published", "in_review"],  # in_review = volver a revisar
    "rejected":  ["draft"],                    # el autor corrige y re-envía
    "published": [],                           # estado final
}

# Transiciones que requieren comentario obligatorio
COMMENT_REQUIRED: set[tuple[str, str]] = {
    ("in_review", "rejected"),
}


class KBWorkflow:
    @staticmethod
    def can_transition(from_status: str, to_status: str) -> bool:
        return to_status in VALID_TRANSITIONS.get(from_status, [])

    @staticmethod
    def validate_transition(
        from_status: str, to_status: str, comment: str | None
    ) -> None:
        """
        Valida que la transición sea permitida y que el comentario esté presente
        cuando sea obligatorio. Lanza WorkflowError si no.
        """
        if not KBWorkflow.can_transition(from_status, to_status):
            allowed = VALID_TRANSITIONS.get(from_status, [])
            raise WorkflowError(
                f"Transición no permitida: {from_status} → {to_status}. "
                f"Permitidas desde '{from_status}': {allowed}"
            )
        if (from_status, to_status) in COMMENT_REQUIRED:
            if not comment or not comment.strip():
                raise WorkflowError(
                    f"Comentario obligatorio al rechazar un artículo "
                    f"({from_status} → {to_status})"
                )
