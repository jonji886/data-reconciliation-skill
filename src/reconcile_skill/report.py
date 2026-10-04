"""Excel and YAML evidence report writers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .models import MappingSpec, ReconciliationResult


def sanitize_excel_cell(value: Any) -> Any:
    """Escape formula-like user strings without converting ordinary numbers."""

    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if not stripped or stripped[0] not in "=+-@":
        return value
    if stripped[0] in "+-":
        try:
            float(stripped.replace(",", ""))
            return value
        except ValueError:
            pass
    # Excel displays a leading apostrophe as an escape marker, not as part of
    # the visible cell value, while openpyxl keeps the value as plain text.
    return "'" + value


def _frame(records: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty and columns:
        return pd.DataFrame(columns=columns)
    return frame


def _safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    safe = frame.copy()
    for column in safe.columns:
        safe[column] = safe[column].map(sanitize_excel_cell)
    return safe


def write_mapping_yaml(
    result: ReconciliationResult,
    output_path: str | Path,
    *,
    source_key: str,
    target_key: str,
    key_case_sensitive: bool = True,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = MappingSpec(
        key={"source": source_key, "target": target_key, "case_sensitive": key_case_sensitive},
        fields=result.mapping,
    )
    payload = {
        "version": spec.version,
        "key": spec.key,
        "fields": [
            {
                "source": rule.source_column,
                "target": rule.target_column,
                "rule": rule.rule_type,
                "tolerance": rule.tolerance,
                "normalizers": rule.normalizers,
                "requires_confirmation": rule.requires_confirmation,
            }
            for rule in spec.fields
        ],
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def write_report(
    result: ReconciliationResult,
    output_dir: str | Path,
    *,
    source_key: str,
    target_key: str,
    source_file: str = "",
    target_file: str = "",
    mapping_suggestions: list[dict[str, Any]] | None = None,
    key_case_sensitive: bool = True,
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "Source Row Count": result.summary.source_row_count,
        "Target Row Count": result.summary.target_row_count,
        "Matched Unique Keys": result.summary.matched_unique_key_count,
        "Missing In Source Keys": result.summary.missing_source_key_count,
        "Missing In Source Rows": result.summary.missing_source_row_count,
        "Missing In Target Keys": result.summary.missing_target_key_count,
        "Missing In Target Rows": result.summary.missing_target_row_count,
        "Duplicate Source Keys": result.summary.duplicate_source_key_count,
        "Duplicate Source Rows": result.summary.duplicate_source_row_count,
        "Duplicate Target Keys": result.summary.duplicate_target_key_count,
        "Duplicate Target Rows": result.summary.duplicate_target_row_count,
        "Value Mismatch Count": result.summary.value_mismatch_count,
        "Key Case Sensitive": key_case_sensitive,
        "Run ID": result.run_id,
        "Run Timestamp": result.run_timestamp.isoformat(),
        "Source File": source_file,
        "Target File": target_file,
        "Source Key": source_key,
        "Target Key": target_key,
        "Warnings": " | ".join(result.warnings),
    }
    mapping_rows = mapping_suggestions or [rule.model_dump() for rule in result.mapping]
    report_path = output / "reconciliation_report.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        _safe_frame(pd.DataFrame([summary]).T.rename(columns={0: "value"})).to_excel(
            writer, sheet_name="Summary", header=True
        )
        _safe_frame(_frame(mapping_rows, ["source_column", "target_column", "mapping_type", "confidence"])).to_excel(
            writer, sheet_name="Mapping", index=False
        )
        _safe_frame(_frame(result.missing_in_source, ["reconciliation_key", "row_number"])).to_excel(
            writer, sheet_name="Missing_In_Source", index=False
        )
        _safe_frame(_frame(result.missing_in_target, ["reconciliation_key", "row_number"])).to_excel(
            writer, sheet_name="Missing_In_Target", index=False
        )
        _safe_frame(_frame(result.duplicate_source, ["reconciliation_key", "duplicate_count", "row_number"])).to_excel(
            writer, sheet_name="Duplicate_Source", index=False
        )
        _safe_frame(_frame(result.duplicate_target, ["reconciliation_key", "duplicate_count", "row_number"])).to_excel(
            writer, sheet_name="Duplicate_Target", index=False
        )
        _safe_frame(
            _frame(
                result.value_mismatch,
                ["reconciliation_key", "source_column", "target_column", "difference_type"],
            )
        ).to_excel(writer, sheet_name="Value_Mismatch", index=False)
        _safe_frame(_frame(result.diagnostics, ["type", "fact", "hypothesis", "confidence"])).to_excel(
            writer, sheet_name="Diagnostics", index=False
        )
    mapping_path = write_mapping_yaml(
        result,
        output / "mapping.yaml",
        source_key=source_key,
        target_key=target_key,
        key_case_sensitive=key_case_sensitive,
    )
    return report_path, mapping_path
