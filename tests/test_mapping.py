import pandas as pd

from reconcile_skill.loaders import LoadedTable
from reconcile_skill.mapping import rules_from_suggestions
from reconcile_skill.profiler import profile_dataframe
from reconcile_skill.semantic_matcher import suggest_column_mappings


def _suggestions(source: dict, target: dict):
    left = LoadedTable(pd.DataFrame(source), "source.csv", None)
    right = LoadedTable(pd.DataFrame(target), "target.csv", None)
    return suggest_column_mappings(
        profile_dataframe(left), profile_dataframe(right), left.dataframe, right.dataframe
    )


def test_order_and_amount_mapping_is_suggested():
    suggestions = _suggestions(
        {"order_id": ["A001", "A002"], "amount": [100, 200]},
        {"order_no": ["A001", "A002"], "total_amount": [100, 200]},
    )
    pairs = {(item.source_column, item.target_column) for item in suggestions}
    assert ("order_id", "order_no") in pairs
    assert ("amount", "total_amount") in pairs


def test_enum_mapping_requires_confirmation():
    suggestions = _suggestions(
        {"order_id": ["A001", "A002"], "status": ["paid", "cancelled"]},
        {"order_no": ["A001", "A002"], "status": ["SUCCESS", "CLOSED"]},
    )
    status = next(item for item in suggestions if item.source_column == "status")
    assert status.mapping_type == "enum"
    assert status.requires_confirmation is True
    try:
        rules_from_suggestions([status])
    except Exception as exc:
        assert exc.code == "AMBIGUOUS_MAPPING"
    else:
        raise AssertionError("enum mapping must not execute without confirmation")
