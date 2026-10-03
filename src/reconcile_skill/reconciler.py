"""Deterministic join, duplicate detection and value comparison."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd

from .diagnosis import diagnose_missing_patterns
from .errors import ReconciliationError
from .models import CompareRule, ReconciliationResult, ReconciliationSummary
from .normalizers import is_null, normalize_key, normalize_value, values_equal


def _records_for_keys(df: pd.DataFrame, key_column: str, keys: set[str | None]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        key = normalize_key(row[key_column])
        if key in keys:
            record = {str(column): (None if is_null(value) else value) for column, value in row.items()}
            record["reconciliation_key"] = key
            records.append(record)
    return records


def _duplicate_records(df: pd.DataFrame, key_column: str) -> list[dict[str, Any]]:
    keys = df[key_column].map(normalize_key)
    counts = keys.value_counts(dropna=False)
    duplicate_keys = {key for key, count in counts.items() if key is not None and count > 1}
    records: list[dict[str, Any]] = []
    for key in sorted(duplicate_keys):
        records.append({"reconciliation_key": key, "count": int(counts[key]), "key_column": key_column})
    return records


def reconcile(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    *,
    source_key: str,
    target_key: str,
    rules: list[CompareRule],
    run_id: str | None = None,
) -> ReconciliationResult:
    for column in [source_key, *[rule.source_column for rule in rules]]:
        if column not in source_df.columns:
            raise ReconciliationError("KEY_NOT_FOUND" if column == source_key else "SCHEMA_ERROR", f"Source 字段不存在: {column}")
    for column in [target_key, *[rule.target_column for rule in rules]]:
        if column not in target_df.columns:
            raise ReconciliationError("KEY_NOT_FOUND" if column == target_key else "SCHEMA_ERROR", f"Target 字段不存在: {column}")

    source_keys = source_df[source_key].map(normalize_key)
    target_keys = target_df[target_key].map(normalize_key)
    source_null_count, target_null_count = int(source_keys.isna().sum()), int(target_keys.isna().sum())
    source_key_set = {key for key in source_keys if key is not None}
    target_key_set = {key for key in target_keys if key is not None}
    source_only, target_only, matched = source_key_set - target_key_set, target_key_set - source_key_set, source_key_set & target_key_set

    duplicate_source = _duplicate_records(source_df, source_key)
    duplicate_target = _duplicate_records(target_df, target_key)
    source_index = {key: index for key, index in zip(source_keys, source_df.index) if key is not None}
    target_index = {key: index for key, index in zip(target_keys, target_df.index) if key is not None}
    mismatches: list[dict[str, Any]] = []
    for key in sorted(matched):
        source_row, target_row = source_df.loc[source_index[key]], target_df.loc[target_index[key]]
        for rule in rules:
            equal, difference_type = values_equal(
                source_row[rule.source_column],
                target_row[rule.target_column],
                rule.rule_type,
                rule.tolerance,
                rule.normalizers,
            )
            if not equal:
                mismatches.append(
                    {
                        "reconciliation_key": key,
                        "source_column": rule.source_column,
                        "target_column": rule.target_column,
                        "source_value": None if is_null(source_row[rule.source_column]) else source_row[rule.source_column],
                        "target_value": None if is_null(target_row[rule.target_column]) else target_row[rule.target_column],
                        "normalized_source_value": normalize_value(
                            source_row[rule.source_column], rule_type=rule.rule_type, normalizers=rule.normalizers
                        ),
                        "normalized_target_value": normalize_value(
                            target_row[rule.target_column], rule_type=rule.rule_type, normalizers=rule.normalizers
                        ),
                        "difference_type": difference_type,
                    }
                )

    warnings: list[str] = []
    if source_null_count or target_null_count:
        warnings.append(f"主键存在空值，未参与 Join：source={source_null_count}, target={target_null_count}")
    if duplicate_source:
        warnings.append("Source 主键不满足唯一性；重复键仅以第一条记录参与字段比较。")
    if duplicate_target:
        warnings.append("Target 主键不满足唯一性；重复键仅以第一条记录参与字段比较。")
    missing_source = _records_for_keys(target_df, target_key, target_only)
    missing_target = _records_for_keys(source_df, source_key, source_only)
    if source_null_count:
        missing_target.extend(_records_for_keys(source_df, source_key, {None}))
    if target_null_count:
        missing_source.extend(_records_for_keys(target_df, target_key, {None}))
    diagnostics = diagnose_missing_patterns(missing_target)
    summary = ReconciliationSummary(
        source_rows=len(source_df),
        target_rows=len(target_df),
        matched_rows=len(matched),
        missing_in_source=len(target_only) + target_null_count,
        missing_in_target=len(source_only) + source_null_count,
        duplicate_source_keys=len(duplicate_source),
        duplicate_target_keys=len(duplicate_target),
        value_mismatches=len(mismatches),
    )
    return ReconciliationResult(
        summary=summary,
        mapping=rules,
        missing_in_source=missing_source,
        missing_in_target=missing_target,
        duplicate_source=duplicate_source,
        duplicate_target=duplicate_target,
        value_mismatch=mismatches,
        diagnostics=diagnostics,
        warnings=warnings,
        run_id=run_id or uuid4().hex,
        run_timestamp=datetime.now(timezone.utc),
    )
