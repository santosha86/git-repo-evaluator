from cli.models import DIMENSION_WEIGHTS, grade_for


def test_weights_sum_to_one() -> None:
    assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9


def test_grade_thresholds() -> None:
    assert grade_for(9.5) == "A+"
    assert grade_for(8.0) == "A"
    assert grade_for(7.0) == "B+"
    assert grade_for(6.0) == "B"
    assert grade_for(5.0) == "C+"
    assert grade_for(4.0) == "C"
    assert grade_for(3.0) == "D"
    assert grade_for(2.99) == "F"
