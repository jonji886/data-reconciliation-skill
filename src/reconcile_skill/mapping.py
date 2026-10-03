"""Mapping suggestions to explicit comparison rules."""

from __future__ import annotations

from .errors import ConfirmationRequired, ReconciliationError
from .models import CompareRule, MappingSuggestion


def suggestion_to_rule(suggestion: MappingSuggestion, *, tolerance: float | None = None, confirmed: bool = False) -> CompareRule:
    if suggestion.target_column is None:
        raise ReconciliationError("SCHEMA_ERROR", f"字段未找到对应目标列: {suggestion.source_column}")
    if suggestion.requires_confirmation and not confirmed:
        raise ConfirmationRequired(
            f"字段 Mapping 需要确认: {suggestion.source_column} -> {suggestion.target_column}",
            details={"suggestion": suggestion.model_dump()},
        )
    normalizers = ["trim", "collapse_whitespace"]
    rule_type = suggestion.mapping_type
    if rule_type == "string":
        normalizers.append("lowercase")
    elif rule_type == "datetime":
        normalizers.append("datetime_parse")
    elif rule_type in {"numeric", "amount"}:
        normalizers.append("numeric_parse")
    return CompareRule(
        source_column=suggestion.source_column,
        target_column=suggestion.target_column,
        rule_type=rule_type,
        tolerance=tolerance,
        normalizers=normalizers,
        requires_confirmation=suggestion.requires_confirmation,
    )


def rules_from_suggestions(
    suggestions: list[MappingSuggestion],
    *,
    confirmed_columns: set[str] | None = None,
    numeric_tolerance: float | None = None,
) -> list[CompareRule]:
    confirmed_columns = confirmed_columns or set()
    rules: list[CompareRule] = []
    for suggestion in suggestions:
        if suggestion.target_column is None:
            continue
        rules.append(
            suggestion_to_rule(
                suggestion,
                tolerance=numeric_tolerance if suggestion.mapping_type in {"numeric", "amount"} else None,
                confirmed=suggestion.source_column in confirmed_columns,
            )
        )
    return rules
