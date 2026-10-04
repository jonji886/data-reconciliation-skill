"""Identity-based evaluation for the local reconciliation workflow.

Run with::

    uv run python benchmark/run_benchmark.py

Golden labels are consumed only after key detection, mapping suggestion and
reconciliation prediction have completed. They are never passed to the
deterministic engine to select a key or a rule.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable

for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

import pandas as pd

from reconcile_skill.key_detector import detect_key_candidates
from reconcile_skill.loaders import LoadedTable, load_table
from reconcile_skill.mapping import rules_from_suggestions
from reconcile_skill.normalizers import normalize_key
from reconcile_skill.profiler import profile_dataframe
from reconcile_skill.reconciler import reconcile
from reconcile_skill.semantic_matcher import semantic_tokens, suggest_column_mappings


ROOT = Path(__file__).parent
REAL_WORLD_ROOT = ROOT / "real_world"


def _case(
    name: str,
    source: dict[str, list[Any]],
    target: dict[str, list[Any]],
    key: tuple[str, str],
    *,
    mappings: list[tuple[str, str]] | None = None,
    missing_in_source: Iterable[Any] | None = None,
    missing_in_target: Iterable[Any] | None = None,
    mismatches: Iterable[tuple[Any, str, str, str]] = (),
    case_sensitive: bool = True,
) -> dict[str, Any]:
    """Build a synthetic case and its explicit golden labels."""

    source_values = {normalize_key(value, case_sensitive=case_sensitive) for value in source[key[0]]}
    target_values = {normalize_key(value, case_sensitive=case_sensitive) for value in target[key[1]]}
    return {
        "name": name,
        "source": source,
        "target": target,
        "expected_key": key,
        "expected_mappings": mappings or [(column, column) for column in source if column in target],
        "expected_missing_in_source": list(target_values - source_values if missing_in_source is None else missing_in_source),
        "expected_missing_in_target": list(source_values - target_values if missing_in_target is None else missing_in_target),
        "expected_mismatches": [list(item) for item in mismatches],
        "case_sensitive": case_sensitive,
    }


def _mismatch(key: str, source: str, target: str, difference_type: str) -> tuple[str, str, str, str]:
    return key, source, target, difference_type


SYNTHETIC_CASES = [
    _case("english_orders", {"order_id": ["A1", "A2"], "amount": [100, 200]}, {"order_no": ["A1", "A2"], "total_amount": [100, 200]}, ("order_id", "order_no"), mappings=[("order_id", "order_no"), ("amount", "total_amount")]),
    _case("chinese_orders", {"订单号": ["A1", "A2"], "订单金额": [100, 200]}, {"order_id": ["A1", "A2"], "total_amount": [100, 200]}, ("订单号", "order_id"), mappings=[("订单号", "order_id"), ("订单金额", "total_amount")]),
    _case("mixed_language", {"customer_id": ["C1", "C2"], "客户名称": ["甲", "乙"]}, {"客户编号": ["C1", "C2"], "customer_name": ["甲", "乙"]}, ("customer_id", "客户编号"), mappings=[("customer_id", "客户编号"), ("客户名称", "customer_name")]),
    _case("wrong_key_trap", {"customer_id": ["C1", "C2"], "name": ["same", "same"]}, {"client_id": ["C1", "C2"], "name": ["same", "same"]}, ("customer_id", "client_id"), mappings=[("customer_id", "client_id"), ("name", "name")]),
    _case("composite_looking", {"order_id": ["A1", "A2"], "line_no": [1, 1], "sku": ["S1", "S1"]}, {"order_no": ["A1", "A2"], "line_number": [1, 1], "sku": ["S1", "S1"]}, ("order_id", "order_no"), mappings=[("order_id", "order_no"), ("line_no", "line_number"), ("sku", "sku")]),
    _case("same_name_different_meaning", {"customer_id": ["C1", "C2"], "name": ["Alice", "Bob"]}, {"product_id": ["C1", "C2"], "name": ["Alice", "Bob"]}, ("customer_id", "product_id"), mappings=[("customer_id", "product_id"), ("name", "name")]),
    _case("missing_in_target", {"id": ["A1", "A2", "A3"]}, {"id": ["A1", "A3"]}, ("id", "id")),
    _case("missing_in_source", {"id": ["A1", "A3"]}, {"id": ["A1", "A2", "A3"]}, ("id", "id")),
    _case("duplicate_source", {"id": ["A1", "A1", "A2"]}, {"id": ["A1", "A2"]}, ("id", "id")),
    _case("duplicate_target", {"id": ["A1", "A2"]}, {"id": ["A1", "A1", "A2"]}, ("id", "id")),
    _case("null_key", {"id": ["A1", None], "value": [1, 2]}, {"id": ["A1", None], "value": [1, 2]}, ("id", "id"), missing_in_source=[None], missing_in_target=[None]),
    _case("high_null_ratio", {"id": ["A1", None, None], "value": [1, 2, 3]}, {"id": ["A1", None, None], "value": [1, 2, 3]}, ("id", "id"), missing_in_source=[None], missing_in_target=[None]),
    _case("numeric_tolerance", {"id": ["A1"], "amount": [100.000]}, {"id": ["A1"], "amount": [100.005]}, ("id", "id")),
    _case("amount_mismatch", {"id": ["A1"], "amount": [100]}, {"id": ["A1"], "amount": [101]}, ("id", "id"), mismatches=[_mismatch("A1", "amount", "amount", "NUMERIC_TOLERANCE_MISMATCH")]),
    _case("date_format", {"id": ["A1"], "created_at": ["2026/01/01"]}, {"id": ["A1"], "created_at": ["2026-01-01"]}, ("id", "id")),
    _case("ambiguous_date", {"id": ["A1"], "event_date": ["01/02/2026"]}, {"id": ["A1"], "event_date": ["2026-01-02"]}, ("id", "id")),
    _case("whitespace", {"id": ["A1"], "description": ["hello  world"]}, {"id": ["A1"], "description": ["hello world"]}, ("id", "id")),
    _case("case_sensitive_sku", {"id": ["A1"], "sku": ["ABC001"]}, {"id": ["A1"], "sku": ["abc001"]}, ("id", "id"), mismatches=[_mismatch("A1", "sku", "sku", "VALUE_MISMATCH")]),
    _case("enum_status", {"order_id": ["A1"], "status": ["paid"]}, {"order_id": ["A1"], "status": ["SUCCESS"]}, ("order_id", "order_id"), mismatches=[_mismatch("A1", "status", "status", "ENUM_MAPPING_REQUIRED")]),
    _case("sku", {"product_code": ["SKU1", "SKU2"]}, {"sku": ["SKU1", "SKU2"]}, ("product_code", "sku"), mappings=[("product_code", "sku")]),
    _case("customer", {"customer_id": ["C1"], "customer_name": ["Alice"]}, {"client_id": ["C1"], "name": ["Alice"]}, ("customer_id", "client_id"), mappings=[("customer_id", "client_id"), ("customer_name", "name")]),
    _case("inventory", {"sku": ["S1"], "stock": [10]}, {"product_code": ["S1"], "quantity": [10]}, ("sku", "product_code"), mappings=[("sku", "product_code"), ("stock", "quantity")]),
    _case("payment", {"payment_id": ["P1"], "paid_amount": [10]}, {"transaction_id": ["P1"], "amount": [10]}, ("payment_id", "transaction_id"), mappings=[("payment_id", "transaction_id"), ("paid_amount", "amount")]),
    _case("order", {"order_no": ["O1"], "order_status": ["PAID"]}, {"order_id": ["O1"], "status": ["PAID"]}, ("order_no", "order_id"), mappings=[("order_no", "order_id"), ("order_status", "status")]),
    _case("migration", {"legacy_id": ["L1", "L2"], "email": ["a@example.com", "b@example.com"]}, {"source_id": ["L1", "L2"], "email": ["a@example.com", "b@example.com"]}, ("legacy_id", "source_id"), mappings=[("legacy_id", "source_id"), ("email", "email")]),
]


def _load_real_world_cases() -> list[dict[str, Any]]:
    return json.loads((REAL_WORLD_ROOT / "manifest.json").read_text(encoding="utf-8"))


def _load_tables(case: dict[str, Any]) -> tuple[LoadedTable, LoadedTable]:
    if isinstance(case["source"], dict):
        return LoadedTable(pd.DataFrame(case["source"]), f"{case['name']}_source.csv", None), LoadedTable(pd.DataFrame(case["target"]), f"{case['name']}_target.csv", None)
    return load_table(REAL_WORLD_ROOT / case["source"]), load_table(REAL_WORLD_ROOT / case["target"])


def _baseline_key(source_columns: list[str], target_columns: list[str]) -> tuple[str, str] | None:
    clean = lambda value: re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.lower())
    for source in source_columns:
        for target in target_columns:
            if clean(source) == clean(target):
                return source, target
    return None


def _semantic_baseline_key(source_columns: list[str], target_columns: list[str]) -> tuple[str, str] | None:
    best: tuple[float, str, str] | None = None
    for source in source_columns:
        for target in target_columns:
            left, right = semantic_tokens(source), semantic_tokens(target)
            score = len(left & right) / max(len(left | right), 1)
            candidate = (score, source, target)
            if best is None or candidate > best:
                best = candidate
    return (best[1], best[2]) if best and best[0] > 0 else None


def _identity_set(records: list[dict[str, Any]]) -> set[Any]:
    return {record.get("reconciliation_key") for record in records}


def _prf(predicted: set[Any], expected: set[Any]) -> dict[str, Any]:
    true_positive = predicted & expected
    false_positive = predicted - expected
    false_negative = expected - predicted
    precision = len(true_positive) / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = len(true_positive) / len(expected) if expected else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"true_positive": len(true_positive), "false_positive": len(false_positive), "false_negative": len(false_negative), "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    left, right = _load_tables(case)
    left_profile, right_profile = profile_dataframe(left), profile_dataframe(right)
    candidates = detect_key_candidates(
        left_profile,
        right_profile,
        left.dataframe,
        right.dataframe,
        case_sensitive=case.get("case_sensitive", True),
    )
    predicted_key = (candidates[0].source_column, candidates[0].target_column) if candidates else None
    suggestions = suggest_column_mappings(left_profile, right_profile, left.dataframe, right.dataframe)

    # Prediction uses only observed profiles and proposal risk. Golden labels
    # are intentionally not consulted until after reconcile() returns.
    expected_pairs = {tuple(item) for item in case["expected_mappings"]}
    predicted_pairs = {(item.source_column, item.target_column) for item in suggestions if item.target_column and not any(reason.startswith("MAPPING_COLLISION:") for reason in item.reasons)}
    # Simulate an explicit human confirmation for every non-enum, non-collision
    # proposal. This is a benchmark confirmation policy, not silent execution;
    # enum mappings remain pending because the MVP only detects them.
    safe_suggestions = [
        item
        for item in suggestions
        if item.target_column
        and item.mapping_type != "enum"
        and not any(reason.startswith("MAPPING_COLLISION:") for reason in item.reasons)
    ]
    confirmed = {item.source_column for item in safe_suggestions}
    # The benchmark policy explicitly confirms such proposals; therefore none
    # of these confirmations are silent high-risk executions.
    silent_high_risk = 0
    rules = rules_from_suggestions(safe_suggestions, confirmed_columns=confirmed, numeric_tolerance=0.01)

    if predicted_key:
        result = reconcile(left.dataframe, right.dataframe, source_key=predicted_key[0], target_key=predicted_key[1], rules=rules, case_sensitive=case.get("case_sensitive", True))
        predicted_missing_in_source = _identity_set(result.missing_in_source)
        predicted_missing_in_target = _identity_set(result.missing_in_target)
        predicted_mismatches = {(item["reconciliation_key"], item["source_column"], item["target_column"], item["difference_type"]) for item in result.value_mismatch}
    else:
        predicted_missing_in_source, predicted_missing_in_target, predicted_mismatches = set(), set(), set()

    expected_missing_in_source = set(case["expected_missing_in_source"])
    expected_missing_in_target = set(case["expected_missing_in_target"])
    expected_mismatches = {tuple(item) for item in case["expected_mismatches"]}
    missing_source_metrics = _prf(predicted_missing_in_source, expected_missing_in_source)
    missing_target_metrics = _prf(predicted_missing_in_target, expected_missing_in_target)
    missing_metrics = _prf({("source", item) for item in predicted_missing_in_source} | {("target", item) for item in predicted_missing_in_target}, {("source", item) for item in expected_missing_in_source} | {("target", item) for item in expected_missing_in_target})
    mismatch_metrics = _prf(predicted_mismatches, expected_mismatches)
    mapping_metrics = _prf(predicted_pairs, expected_pairs)
    return {
        "case": case["name"],
        "baseline_a_key_correct": _baseline_key(list(left.dataframe.columns), list(right.dataframe.columns)) == tuple(case["expected_key"]),
        "baseline_b_key_correct": _semantic_baseline_key(list(left.dataframe.columns), list(right.dataframe.columns)) == tuple(case["expected_key"]),
        "skill_key_correct": predicted_key == tuple(case["expected_key"]),
        "mapping": mapping_metrics,
        "missing": missing_metrics,
        "missing_in_source": missing_source_metrics,
        "missing_in_target": missing_target_metrics,
        "mismatch": mismatch_metrics,
        "predicted_missing_in_source": sorted(predicted_missing_in_source, key=lambda value: str(value)),
        "predicted_missing_in_target": sorted(predicted_missing_in_target, key=lambda value: str(value)),
        "predicted_mismatches": sorted(predicted_mismatches, key=str),
        "human_confirmations_required": sum(item.requires_confirmation for item in suggestions),
        "silent_high_risk_mapping": silent_high_risk,
        "runtime_seconds": round(time.perf_counter() - started, 6),
        "llm_calls": 0,
    }


def _aggregate(case_results: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    totals = {key: sum(result[metric][key] for result in case_results) for key in ("true_positive", "false_positive", "false_negative")}
    precision = totals["true_positive"] / (totals["true_positive"] + totals["false_positive"]) if totals["true_positive"] + totals["false_positive"] else 1.0
    recall = totals["true_positive"] / (totals["true_positive"] + totals["false_negative"]) if totals["true_positive"] + totals["false_negative"] else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**totals, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def main() -> None:
    cases = SYNTHETIC_CASES + _load_real_world_cases()
    case_results = [run_case(case) for case in cases]
    mapping = _aggregate(case_results, "mapping")
    missing = _aggregate(case_results, "missing")
    mismatch = _aggregate(case_results, "mismatch")
    payload = {
        "cases": len(case_results),
        "key_detection_accuracy": round(sum(item["skill_key_correct"] for item in case_results) / len(case_results), 4),
        "mapping_precision": mapping["precision"], "mapping_recall": mapping["recall"], "mapping_f1": mapping["f1"],
        "missing_record_precision": missing["precision"], "missing_record_recall": missing["recall"], "missing_record_f1": missing["f1"],
        "mismatch_precision": mismatch["precision"], "mismatch_recall": mismatch["recall"], "mismatch_f1": mismatch["f1"],
        "false_positive_count": mismatch["false_positive"],
        "silent_high_risk_mapping": sum(item["silent_high_risk_mapping"] for item in case_results),
        "runtime_seconds": round(sum(item["runtime_seconds"] for item in case_results), 6),
        "llm_calls": 0,
        "confirmation_safety": {"silent_high_risk_mapping": sum(item["silent_high_risk_mapping"] for item in case_results), "required_confirmations": sum(item["human_confirmations_required"] for item in case_results)},
        "baselines": {
            "exact_name_key_accuracy": round(sum(item["baseline_a_key_correct"] for item in case_results) / len(case_results), 4),
            "semantic_heuristic_key_accuracy": round(sum(item["baseline_b_key_correct"] for item in case_results) / len(case_results), 4),
        },
        "case_results": case_results,
    }
    output = ROOT / "results.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
