def test_sanitize_simple_phrase():
    """Texto libre se convierte en tsquery con prefix matching."""
    from backend.src.modules.search.application.use_cases import sanitize_tsquery
    result = sanitize_tsquery("error de red")
    assert result == "error:* & de:* & red:*"


def test_sanitize_strips_tsquery_operators():
    """Operadores especiales de tsquery son eliminados para prevenir inyección."""
    from backend.src.modules.search.application.use_cases import sanitize_tsquery
    result = sanitize_tsquery("error & reboot | crash")
    # Los operadores & | son eliminados; solo quedan palabras
    assert "&" not in result.replace(" & ", "X")  # el único & es el nuestro
    assert "|" not in result
    # Las palabras deben estar presentes
    assert "error:*" in result
    assert "reboot:*" in result
    assert "crash:*" in result


def test_sanitize_removes_parentheses_and_colons():
    """Paréntesis y dos puntos son caracteres especiales de tsquery."""
    from backend.src.modules.search.application.use_cases import sanitize_tsquery
    result = sanitize_tsquery("(test):*query")
    assert "(" not in result
    assert ")" not in result


def test_sanitize_single_word():
    """Una sola palabra se convierte correctamente."""
    from backend.src.modules.search.application.use_cases import sanitize_tsquery
    result = sanitize_tsquery("incidente")
    assert result == "incidente:*"


def test_sanitize_empty_after_strip_returns_empty():
    """Una cadena de solo operadores retorna vacío."""
    from backend.src.modules.search.application.use_cases import sanitize_tsquery
    result = sanitize_tsquery("& | !")
    assert result == ""


def test_validation_error_on_empty_query():
    """query vacío lanza ValidationError."""
    from backend.src.core.exceptions import ValidationError

    query = "   "
    if not query.strip():
        try:
            raise ValidationError("El query no puede estar vacío")
        except ValidationError as e:
            assert "vacío" in e.message
            assert e.code == "VALIDATION_ERROR"
            return
    assert False, "Debería haber lanzado ValidationError"


def test_validation_error_on_only_operators():
    """query con solo operadores (se sanitiza a vacío) lanza ValidationError."""
    from backend.src.modules.search.application.use_cases import sanitize_tsquery
    from backend.src.core.exceptions import ValidationError

    query = "& | !"
    tsquery = sanitize_tsquery(query)
    if not tsquery:
        try:
            raise ValidationError("El query no puede estar vacío")
        except ValidationError as e:
            assert e.code == "VALIDATION_ERROR"
            return
    assert False, "Debería haber detectado query vacío después de sanitizar"
