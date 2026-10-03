"""Rule-based difference pattern diagnosis."""

from __future__ import annotations

from typing import Any

import pandas as pd


def diagnose_missing_patterns(
    missing_records: list[dict[str, Any]],
    *,
    threshold: float = 0.7,
    minimum_count: int = 2,
) -> list[dict[str, Any]]:
    if not missing_records:
        return []
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
                    "fact": f"{count} of {len(values)} missing records have {column}={value}.",
                    "hypothesis": f"Target dataset may apply a filtering rule related to {column}={value}.",
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
