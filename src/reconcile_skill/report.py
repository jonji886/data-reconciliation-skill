"""Excel and YAML evidence report writers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .models import MappingSpec, ReconciliationResult


def _frame(records: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty and columns:
        return pd.DataFrame(columns=columns)
    return frame


def write_mapping_yaml(result: ReconciliationResult, output_path: str | Path, *, source_key: str, target_key: str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = MappingSpec(key={"source": source_key, "target": target_key}, fields=result.mapping)
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
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = result.summary.model_dump()
    summary.update(
        {
            "run_id": result.run_id,
            "run_timestamp": result.run_timestamp.isoformat(),
            "source_file": source_file,
            "target_file": target_file,
            "source_key": source_key,
            "target_key": target_key,
            "warnings": " | ".join(result.warnings),
        }
    )
    mapping_rows = mapping_suggestions or [rule.model_dump() for rule in result.mapping]
    report_path = output / "reconciliation_report.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        pd.DataFrame([summary]).T.rename(columns={0: "value"}).to_excel(writer, sheet_name="Summary", header=True)
        _frame(mapping_rows).to_excel(writer, sheet_name="Mapping", index=False)
        _frame(result.missing_in_source).to_excel(writer, sheet_name="Missing_In_Source", index=False)
        _frame(result.missing_in_target).to_excel(writer, sheet_name="Missing_In_Target", index=False)
        _frame(result.duplicate_source).to_excel(writer, sheet_name="Duplicate_Source", index=False)
        _frame(result.duplicate_target).to_excel(writer, sheet_name="Duplicate_Target", index=False)
        _frame(result.value_mismatch).to_excel(writer, sheet_name="Value_Mismatch", index=False)
        _frame(result.diagnostics).to_excel(writer, sheet_name="Diagnostics", index=False)
    mapping_path = write_mapping_yaml(result, output / "mapping.yaml", source_key=source_key, target_key=target_key)
    return report_path, mapping_path
