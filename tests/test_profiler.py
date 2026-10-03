import pandas as pd

from reconcile_skill.loaders import LoadedTable
from reconcile_skill.profiler import profile_dataframe


def test_profile_contains_required_statistics():
    table = LoadedTable(
        pd.DataFrame({"order_id": ["A001", "A002", None], "amount": [100, 200, 200]}),
        "source.csv",
        None,
    )
    profile = profile_dataframe(table)
    assert profile.row_count == 3
    assert profile.column_count == 2
    amount = next(column for column in profile.columns if column.name == "amount")
    assert amount.null_ratio == 0
    assert amount.unique_ratio == 2 / 3
    assert amount.min == 100
    assert amount.max == 200
