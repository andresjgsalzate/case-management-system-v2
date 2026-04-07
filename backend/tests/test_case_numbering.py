def test_format_case_number_default():
    from backend.src.modules.cases.application.number_service import format_case_number
    assert format_case_number("CASE", 4, 1) == "CASE-0001"


def test_format_case_number_padding_5():
    from backend.src.modules.cases.application.number_service import format_case_number
    assert format_case_number("INC", 5, 42) == "INC-00042"


def test_format_case_number_exceeds_padding():
    from backend.src.modules.cases.application.number_service import format_case_number
    # Con padding 4, el número 10000 supera el padding → debe mostrar 5 dígitos
    assert format_case_number("CASE", 4, 10000) == "CASE-10000"


def test_format_case_number_prefix_uppercase():
    from backend.src.modules.cases.application.number_service import format_case_number
    assert format_case_number("tk", 4, 1) == "TK-0001"
