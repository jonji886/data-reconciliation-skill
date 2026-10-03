import pandas as pd

from reconcile_skill.models import CompareRule
from reconcile_skill.reconciler import reconcile


def test_missing_duplicate_and_mismatch_summary():
    source = pd.DataFrame({"order_id": ["A001", "A001", "A002", "A003"], "amount": [100, 100, 200, 300]})
    target = pd.DataFrame({"order_no": ["A001", "A002", "A004"], "total_amount": [100, 201, 400]})
    result = reconcile(
        source,
        target,
        source_key="order_id",
        target_key="order_no",
        rules=[CompareRule(source_column="amount", target_column="total_amount", rule_type="numeric", tolerance=0.01, normalizers=["numeric_parse"])],
    )
    assert result.summary.matched_rows == 2
    assert result.summary.missing_in_target == 1
    assert result.summary.missing_in_source == 1
    assert result.summary.duplicate_source_keys == 1
    assert result.summary.value_mismatches == 1
    assert result.value_mismatch[0]["reconciliation_key"] == "a002"


def test_format_and_date_differences_are_not_false_mismatches():
    source = pd.DataFrame({"id": ["A001"], "name": [" Alice "], "date": ["2026/10/01"]})
    target = pd.DataFrame({"id": ["A001"], "name": ["alice"], "date": ["2026-10-01"]})
    result = reconcile(
        source,
        target,
        source_key="id",
        target_key="id",
        rules=[
            CompareRule(source_column="name", target_column="name", rule_type="string", normalizers=["trim", "lowercase"]),
            CompareRule(source_column="date", target_column="date", rule_type="datetime", normalizers=["datetime_parse"]),
        ],
    )
    assert result.summary.value_mismatches == 0
