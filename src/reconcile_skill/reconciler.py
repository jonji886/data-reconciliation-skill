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


def _row_record(row: pd.Series, *, reconciliation_key: str | None, row_number: int) -> dict[str, Any]:
    record = {str(column): (None if is_null(value) else value) for column, value in row.items()}
    record["reconciliation_key"] = reconciliation_key
    record["row_number"] = row_number
    return record


def _records_for_keys(
    df: pd.DataFrame,
    key_column: str,
    keys: set[str | None],
    *,
    case_sensitive: bool = True,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row_number, (_, row) in enumerate(df.iterrows(), start=1):
        key = normalize_key(row[key_column], case_sensitive=case_sensitive)
        if key in keys:
            records.append(_row_record(row, reconciliation_key=key, row_number=row_number))
    return records


def _duplicate_records(
    df: pd.DataFrame,
    key_column: str,
    *,
    case_sensitive: bool = True,
) -> list[dict[str, Any]]:
    keys = df[key_column].map(lambda value: normalize_key(value, case_sensitive=case_sensitive))
    counts = keys.value_counts(dropna=False)
    duplicate_keys = {key for key, count in counts.items() if key is not None and count > 1}
    records: list[dict[str, Any]] = []
    for row_number, (_, row) in enumerate(df.iterrows(), start=1):
        key = normalize_key(row[key_column], case_sensitive=case_sensitive)
        if key in duplicate_keys:
            record = _row_record(row, reconciliation_key=key, row_number=row_number)
            record["duplicate_count"] = int(counts[key])
            record["key_column"] = key_column
            records.append(record)
    return records


def reconcile(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    *,
    source_key: str,
    target_key: str,
    rules: list[CompareRule],
    run_id: str | None = None,
    case_sensitive: bool = True,
) -> ReconciliationResult:
    target_to_sources: dict[str, list[str]] = {}
    for rule in rules:
        target_to_sources.setdefault(rule.target_column, []).append(rule.source_column)
    collisions = {target: sources for target, sources in target_to_sources.items() if len(sources) > 1}
    if collisions:
        raise ReconciliationError(
            "MAPPING_COLLISION",
            "多个 Source 字段映射到同一 Target 字段，普通一对一 Mapping 不允许继续执行。",
            details={"collisions": collisions},
        )
    for column in [source_key, *[rule.source_column for rule in rules]]:
        if column not in source_df.columns:
            raise ReconciliationError("KEY_NOT_FOUND" if column == source_key else "SCHEMA_ERROR", f"Source 字段不存在: {column}")
    for column in [target_key, *[rule.target_column for rule in rules]]:
        if column not in target_df.columns:
            raise ReconciliationError("KEY_NOT_FOUND" if column == target_key else "SCHEMA_ERROR", f"Target 字段不存在: {column}")

    key_normalizer = lambda value: normalize_key(value, case_sensitive=case_sensitive)
    source_keys = source_df[source_key].map(key_normalizer)
    target_keys = target_df[target_key].map(key_normalizer)
    source_null_count, target_null_count = int(source_keys.isna().sum()), int(target_keys.isna().sum())
    source_key_set = {key for key in source_keys if key is not None}
    target_key_set = {key for key in target_keys if key is not None}
    source_only, target_only, matched = source_key_set - target_key_set, target_key_set - source_key_set, source_key_set & target_key_set

    duplicate_source = _duplicate_records(source_df, source_key, case_sensitive=case_sensitive)
    duplicate_target = _duplicate_records(target_df, target_key, case_sensitive=case_sensitive)
    duplicate_source_keys = {record["reconciliation_key"] for record in duplicate_source}
    duplicate_target_keys = {record["reconciliation_key"] for record in duplicate_target}
    safe_matched = matched - duplicate_source_keys - duplicate_target_keys
    source_index = {
        key: position for position, key in enumerate(source_keys) if key is not None and key not in duplicate_source_keys
    }
    target_index = {
        key: position for position, key in enumerate(target_keys) if key is not None and key not in duplicate_target_keys
    }
    mismatches: list[dict[str, Any]] = []
    for key in sorted(safe_matched):
        source_row, target_row = source_df.iloc[source_index[key]], target_df.iloc[target_index[key]]
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
        warnings.append("Source 主键不满足唯一性；Duplicate keys are excluded from normal record-level comparison.")
    if duplicate_target:
        warnings.append("Target 主键不满足唯一性；Duplicate keys are excluded from normal record-level comparison.")
    missing_source = _records_for_keys(target_df, target_key, target_only, case_sensitive=case_sensitive)
    missing_target = _records_for_keys(source_df, source_key, source_only, case_sensitive=case_sensitive)
    if source_null_count:
        missing_target.extend(_records_for_keys(source_df, source_key, {None}, case_sensitive=case_sensitive))
    if target_null_count:
        missing_source.extend(_records_for_keys(target_df, target_key, {None}, case_sensitive=case_sensitive))
    diagnostics = diagnose_missing_patterns(missing_target)
    summary = ReconciliationSummary(
        source_row_count=len(source_df),
        target_row_count=len(target_df),
        matched_key_count=len(safe_matched),
        matched_unique_key_count=len(safe_matched),
        missing_source_key_count=len(target_only),
        missing_source_row_count=len(missing_source),
        missing_target_key_count=len(source_only),
        missing_target_row_count=len(missing_target),
        duplicate_source_key_count=len(duplicate_source_keys),
        duplicate_source_row_count=len(duplicate_source),
        duplicate_target_key_count=len(duplicate_target_keys),
        duplicate_target_row_count=len(duplicate_target),
        value_mismatch_count=len(mismatches),
        source_rows=len(source_df),
        target_rows=len(target_df),
        matched_rows=len(safe_matched),
        missing_in_source=len(missing_source),
        missing_in_target=len(missing_target),
        duplicate_source_keys=len(duplicate_source_keys),
        duplicate_target_keys=len(duplicate_target_keys),
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
