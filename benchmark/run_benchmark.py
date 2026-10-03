"""Small repeatable benchmark for the local heuristic workflow.

Run with: uv run python benchmark/run_benchmark.py
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

import pandas as pd

from reconcile_skill.key_detector import detect_key_candidates
from reconcile_skill.loaders import LoadedTable
from reconcile_skill.models import CompareRule
from reconcile_skill.profiler import profile_dataframe
from reconcile_skill.reconciler import reconcile
from reconcile_skill.semantic_matcher import suggest_column_mappings


def _baseline_key(source_columns: list[str], target_columns: list[str]) -> tuple[str, str] | None:
    """Baseline A: only exact normalized column names are considered keys."""
    clean = lambda value: re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.lower())
    for source in source_columns:
        for target in target_columns:
            if clean(source) == clean(target):
                return source, target
    return None


def run_case(name: str, source: dict, target: dict, expected_key: tuple[str, str]) -> dict:
    started = time.perf_counter()
    left = LoadedTable(pd.DataFrame(source), f"{name}_source.csv", None)
    right = LoadedTable(pd.DataFrame(target), f"{name}_target.csv", None)
    left_profile, right_profile = profile_dataframe(left), profile_dataframe(right)
    candidates = detect_key_candidates(left_profile, right_profile, left.dataframe, right.dataframe)
    key = candidates[0] if candidates else None
    mappings = suggest_column_mappings(left_profile, right_profile, left.dataframe, right.dataframe)
    confirmed = [item for item in mappings if item.target_column and not item.requires_confirmation]
    rules = [
        CompareRule(source_column=item.source_column, target_column=item.target_column, rule_type=item.mapping_type, normalizers=["trim", "lowercase"])
        for item in confirmed
    ]
    result = reconcile(left.dataframe, right.dataframe, source_key=expected_key[0], target_key=expected_key[1], rules=rules)
    baseline_key = _baseline_key(list(left.dataframe.columns), list(right.dataframe.columns))
    expected_missing = len(set(left.dataframe[expected_key[0]]) - set(right.dataframe[expected_key[1]]))
    return {
        "case": name,
        "baseline_key_correct": baseline_key == expected_key,
        "skill_key_correct": bool(key and (key.source_column, key.target_column) == expected_key),
        "mapping_suggestions": len(mappings),
        "human_confirmations_required": sum(item.requires_confirmation for item in mappings),
        "missing_record_recall": round(result.summary.missing_in_target / expected_missing, 4) if expected_missing else 1.0,
        "false_positive_count": result.summary.value_mismatches,
        "runtime_ms": round((time.perf_counter() - started) * 1000, 2),
        "llm_calls": 0,
        "estimated_token_usage": 0,
    }


def main() -> None:
    cases = [
        run_case(
            "orders",
            {"order_id": ["A001", "A002"], "amount": [100, 200]},
            {"order_no": ["A001", "A002"], "total_amount": [100, 200]},
            ("order_id", "order_no"),
        ),
        run_case(
            "customers",
            {"customer_id": ["C001", "C002", "C003"], "name": ["Alice", "Bob", "Cara"]},
            {"client_id": ["C001", "C003"], "name": ["Alice", "Cara"]},
            ("customer_id", "client_id"),
        ),
    ]
    print(json.dumps(cases, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
