"""Rule-based difference pattern diagnosis."""

from __future__ import annotations

from typing import Any

import pandas as pd


def diagnose_missing_patterns(
    missing_records: list[dict[str, Any]],
    *,
    direction: str = "Missing_In_Target",
    threshold: float = 0.7,
    minimum_count: int = 2,
) -> list[dict[str, Any]]:
    if not missing_records:
        return []
    if len(missing_records) < minimum_count:
        return [
            {
                "type": "LOW_SAMPLE",
                "direction": direction,
                "fact": f"{len(missing_records)} missing record is available for {direction}; no reliable pattern was inferred.",
                "hypothesis": "Insufficient sample size for a business pattern hypothesis.",
                "confidence": "LOW",
                "evidence_count": len(missing_records),
                "evidence_total": len(missing_records),
                "ratio": 1.0,
                "note": "Low sample; this is not a root-cause conclusion.",
            }
        ]
    frame = pd.DataFrame(missing_records)
    diagnostics: list[dict[str, Any]] = []
    for column in frame.columns:
        if column.startswith("__") or column in {"reconciliation_key"}:
            continue
        values = frame[column].dropna().astype(str)
        if values.empty or values.nunique() <= 1 and len(values) < minimum_count:
            continue
        counts = values.value_counts()
        value = str(counts.index[0])
        count = int(counts.iloc[0])
        ratio = count / len(values)
        if count >= minimum_count and ratio >= threshold:
            diagnostics.append(
                {
                    "type": "PATTERN",
                    "direction": direction,
                    "fact": f"{count} of {len(values)} missing records have {column}={value}.",
                    "hypothesis": (
                        f"Source dataset may omit or filter records related to {column}={value}."
                        if direction == "Missing_In_Source"
                        else f"Target dataset may omit or filter records related to {column}={value}."
                    ),
                    "confidence": "HIGH" if ratio >= 0.85 else "MEDIUM",
                    "evidence_count": count,
                    "evidence_total": len(values),
                    "ratio": round(ratio, 4),
                    "column": column,
                    "value": value,
                    "note": "Hypothesis only; this does not prove root cause.",
                }
            )
    diagnostics.sort(key=lambda item: (-item["ratio"], item["column"]))
    return diagnostics
