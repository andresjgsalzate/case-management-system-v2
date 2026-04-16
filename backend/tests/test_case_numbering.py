def test_format_range_number_default():
    from backend.src.modules.cases.application.number_service import format_range_number
    assert format_range_number("CASE", 1) == "CASE000001"


def test_format_range_number_large():
    from backend.src.modules.cases.application.number_service import format_range_number
    assert format_range_number("INC", 42) == "INC000042"


def test_format_range_number_exceeds_padding():
    from backend.src.modules.cases.application.number_service import format_range_number
    # Números mayores a 999999 superan el padding de 6 → se muestran tal cual
    assert format_range_number("CASE", 1000000) == "CASE1000000"


def test_format_range_number_prefix_uppercase():
    from backend.src.modules.cases.application.number_service import format_range_number
    assert format_range_number("tk", 1) == "TK000001"
