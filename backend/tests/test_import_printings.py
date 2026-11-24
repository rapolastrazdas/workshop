import pytest

from app.card_import import parse_card_list


@pytest.mark.parametrize("text, name, quantity", [
    ("1 Sol Ring (C21) 263", "sol ring", 1),
    ("4x LIGHTNING BOLT (m10) 146", "lightning bolt", 4),
    ("Sol Ring (C21) 263", "sol ring", 1),
    ("Sol Ring (C21)", "sol ring", 1),
    ("1 Sol Ring", "sol ring", 1),
    ("1 Urza’s, Saga (MH2) 259", "urzas saga", 1),
    ("1 Fable of the Mirror-Breaker // Reflection of Kiki (NEO) 141", "fable of the mirror-breaker // reflection of kiki", 1),
    ("1 B.F.M. (Big Furry Monster)", "b.f.m. (big furry monster)", 1),
])
def test_optional_printing_suffix_does_not_change_oracle_name(text, name, quantity):
    lines, unrecognized = parse_card_list(text)
    assert unrecognized == []
    assert len(lines) == 1
    assert lines[0].text == text
    assert lines[0].name == name
    assert lines[0].quantity == quantity


def test_printing_lines_keep_maybeboard_context_and_invalid_quantities():
    lines, unrecognized = parse_card_list("0 Sol Ring (C21) 263\nMaybeboard\n2x Sol Ring (C21) 263")
    assert [(line.name, line.quantity, line.list_name) for line in lines] == [("sol ring", 2, "maybeboard")]
    assert unrecognized[0].text == "0 Sol Ring (C21) 263"
