"""Configurable, conservative value normalization."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

NULL_TOKENS = {"", "null", "none", "nan", "n/a", "na"}


def is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in NULL_TOKENS:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_key(
    value: Any,
    *,
    trim: bool = True,
    collapse_whitespace: bool = True,
    case_sensitive: bool = True,
) -> str | None:
    """Normalize a join key without changing identifier case by default.

    Case folding is an explicit business rule because values such as ``ABC001``
    and ``abc001`` can represent different identifiers in enterprise systems.
    """

    if is_null(value):
        return None
    text = str(value)
    if trim:
        text = text.strip()
    if collapse_whitespace:
        text = re.sub(r"\s+", " ", text)
    if not case_sensitive:
        text = text.lower()
    return text


def parse_number(value: Any) -> Decimal | None:
    if is_null(value):
        return None
    if isinstance(value, bool):
        return Decimal(int(value))
    text = str(value).strip().replace(",", "")
    text = re.sub(r"[^0-9eE+\-.]", "", text)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_datetime(value: Any) -> pd.Timestamp | None:
    if is_null(value):
        return None
    try:
        result = pd.to_datetime(value, errors="coerce")
        if pd.isna(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def normalize_value(value: Any, *, rule_type: str = "string", normalizers: list[str] | None = None) -> Any:
    normalizers = normalizers or []
    if is_null(value):
        return None
    if rule_type in {"number", "amount", "numeric"} or "numeric_parse" in normalizers:
        parsed = parse_number(value)
        if parsed is not None:
            value = parsed
    elif rule_type == "datetime" or "datetime_parse" in normalizers:
        parsed_dt = parse_datetime(value)
        if parsed_dt is not None:
            value = parsed_dt.isoformat()
    if isinstance(value, (Decimal, float, int)) and not isinstance(value, bool):
        return value
    text = str(value)
    if "trim" in normalizers or rule_type in {"string", "enum", "identifier", "name"}:
        text = text.strip()
    if "collapse_whitespace" in normalizers:
        text = re.sub(r"\s+", " ", text)
    if "lowercase" in normalizers:
        text = text.lower()
    if "uppercase" in normalizers:
        text = text.upper()
    return text


def values_equal(left: Any, right: Any, rule_type: str, tolerance: float | None, normalizers: list[str]) -> tuple[bool, str]:
    left_normalized = normalize_value(left, rule_type=rule_type, normalizers=normalizers)
    right_normalized = normalize_value(right, rule_type=rule_type, normalizers=normalizers)
    if left_normalized is None and right_normalized is None:
        return True, "MATCH"
    if left_normalized is None or right_normalized is None:
        return False, "NULL_MISMATCH"
    if rule_type in {"number", "amount", "numeric"}:
        left_number, right_number = parse_number(left_normalized), parse_number(right_normalized)
        if left_number is not None and right_number is not None:
            difference = abs(left_number - right_number)
            if tolerance is not None and difference <= Decimal(str(tolerance)):
                return True, "MATCH_WITHIN_TOLERANCE"
            return difference == 0, "NUMERIC_TOLERANCE_MISMATCH" if difference else "MATCH"
    if left_normalized == right_normalized:
        if str(left) != str(right):
            return True, "FORMAT_ONLY_DIFFERENCE"
        return True, "MATCH"
    if rule_type == "datetime":
        return False, "DATETIME_MISMATCH"
    if rule_type == "enum":
        return False, "ENUM_MAPPING_REQUIRED"
    return False, "VALUE_MISMATCH"
