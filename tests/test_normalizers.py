import pandas as pd

from reconcile_skill.normalizers import normalize_value, values_equal


def test_numeric_tolerance():
    equal, kind = values_equal("100.000", "100.005", "numeric", 0.01, ["numeric_parse"])
    assert equal is True
    assert kind == "MATCH_WITHIN_TOLERANCE"


def test_trim_and_case_normalization():
    equal, kind = values_equal("  Alice ", "alice", "string", None, ["trim", "lowercase"])
    assert equal is True
    assert kind == "FORMAT_ONLY_DIFFERENCE"


def test_datetime_normalization():
    left = normalize_value("2026/10/01", rule_type="datetime", normalizers=["datetime_parse"])
    right = normalize_value("2026-10-01", rule_type="datetime", normalizers=["datetime_parse"])
    assert pd.Timestamp(left) == pd.Timestamp(right)
