def test_valid_transition_draft_to_in_review():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("draft", "in_review") is True


def test_valid_transition_in_review_to_approved():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("in_review", "approved") is True


def test_valid_transition_in_review_to_rejected():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("in_review", "rejected") is True


def test_valid_transition_approved_to_published():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("approved", "published") is True


def test_valid_transition_approved_back_to_in_review():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("approved", "in_review") is True


def test_valid_transition_rejected_to_draft():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("rejected", "draft") is True


def test_invalid_transition_draft_to_published():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("draft", "published") is False


def test_invalid_transition_published_to_draft():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    assert KBWorkflow.can_transition("published", "draft") is False


def test_invalid_transition_published_has_no_exits():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow, VALID_TRANSITIONS
    assert VALID_TRANSITIONS["published"] == []
    assert KBWorkflow.can_transition("published", "approved") is False


def test_rejection_requires_comment():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow, WorkflowError
    try:
        KBWorkflow.validate_transition("in_review", "rejected", comment=None)
        assert False, "Debería haber lanzado WorkflowError"
    except WorkflowError as e:
        assert "comentario obligatorio" in e.message.lower()


def test_rejection_with_empty_string_requires_comment():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow, WorkflowError
    try:
        KBWorkflow.validate_transition("in_review", "rejected", comment="   ")
        assert False, "Debería haber lanzado WorkflowError"
    except WorkflowError:
        pass


def test_rejection_with_comment_passes():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
    # No debe lanzar excepción
    KBWorkflow.validate_transition("in_review", "rejected", comment="El contenido es incorrecto")


def test_invalid_transition_raises_workflow_error():
    from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow, WorkflowError
    try:
        KBWorkflow.validate_transition("draft", "published", comment=None)
        assert False, "Debería haber lanzado WorkflowError"
    except WorkflowError as e:
        assert "no permitida" in e.message.lower()


def test_workflow_error_is_business_rule_error():
    """WorkflowError hereda de BusinessRuleError para ser capturado por el handler HTTP."""
    from backend.src.modules.knowledge_base.application.review_workflow import WorkflowError
    from backend.src.core.exceptions import BusinessRuleError
    assert issubclass(WorkflowError, BusinessRuleError)
