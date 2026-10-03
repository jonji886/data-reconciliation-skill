import pandas as pd

from reconcile_skill.key_detector import detect_key_candidates
from reconcile_skill.loaders import LoadedTable
from reconcile_skill.profiler import profile_dataframe


def test_id_alias_beats_non_unique_name():
    source = LoadedTable(pd.DataFrame({"customer_id": ["C001", "C002"], "name": ["Alice", "Alice"]}), "s.csv", None)
    target = LoadedTable(pd.DataFrame({"client_id": ["C001", "C002"], "name": ["Alice", "Alice"]}), "t.csv", None)
    candidates = detect_key_candidates(
        profile_dataframe(source), profile_dataframe(target), source.dataframe, target.dataframe
    )
    assert candidates[0].source_column == "customer_id"
    assert candidates[0].target_column == "client_id"
    assert candidates[0].score >= 0.95
