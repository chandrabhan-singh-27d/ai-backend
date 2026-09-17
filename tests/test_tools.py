from app.services.tools import calculate


def test_basic_arithmetic() -> None:
    assert calculate("2 + 3 * 4") == "14"
    assert calculate("(2 + 3) * 4") == "20"
    assert calculate("2 ** 10") == "1024"
    assert calculate("10 / 4") == "2.5"
    assert calculate("-5 + 3") == "-2"


def test_whitelisted_functions() -> None:
    assert calculate("sqrt(16)") == "4.0"
    assert calculate("abs(-7)") == "7"
    assert calculate("round(3.14159)") == "3"
    assert calculate("max(3, 7)") == "7"
    assert calculate("min(3, 7)") == "3"


def test_constants() -> None:
    assert calculate("pi") == str(3.141592653589793)
    assert calculate("round(e)") == "3"


def test_division_by_zero_is_an_error_message() -> None:
    assert calculate("1 / 0").startswith("Error:")


def test_attribute_access_is_rejected() -> None:
    result = calculate("().__class__.__bases__[0].__subclasses__()")
    assert result.startswith("Error:")


def test_import_is_rejected() -> None:
    assert calculate("__import__('os')").startswith("Error:")


def test_string_literals_are_rejected() -> None:
    assert calculate("'shell text'").startswith("Error:")


def test_lambda_and_comprehensions_are_rejected() -> None:
    assert calculate("lambda: 1").startswith("Error:")
    assert calculate("[x for x in range(3)]").startswith("Error:")