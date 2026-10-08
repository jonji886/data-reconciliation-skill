"""Configurable, conservative value normalization.

Normalization is deliberately strict. A value that cannot be parsed under
the selected rule is returned as an unverified comparison instead of being
cleaned until it happens to look numeric or dated.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real
from typing import Any

import pandas as pd

from .models import ComparisonStatus, ValueComparison

NULL_TOKENS = {"", "null", "none", "nan", "n/a", "na"}
_NON_FINITE_TOKENS = {
    "nan", "+nan", "-nan", "inf", "+inf", "-inf",
    "infinity", "+infinity", "-infinity",
}

# A comma is legal only as a conventional three-digit grouping separator.
_NUMBER_RE = re.compile(
    r"^[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
)
_DATE_RE = re.compile(
    r"^(?P<year>\d{4})(?P<date_sep>-|/)(?P<month>\d{2})(?P=date_sep)(?P<day>\d{2})"
    r"(?:[ T](?P<hour>\d{2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?:\.(?P<fraction>\d{1,6}))?)?"
    r"(?P<tz>Z|[+-]\d{2}:?\d{2})?)?$"
)


def is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in NULL_TOKENS:
        return True
    try:
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False
    except (TypeError, ValueError):
        return False


def _is_non_finite_numeric(value: Any) -> bool:
    """Return True for explicit NaN/Infinity values, not ordinary nulls."""

    if isinstance(value, str):
        return value.strip().lower() in _NON_FINITE_TOKENS
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, Decimal):
        return not value.is_finite()
    if isinstance(value, Real):
        try:
            return not math.isfinite(float(value))
        except (OverflowError, ValueError):
            return True
    return False


def normalize_key(
    value: Any,
    *,
    trim: bool = True,
    collapse_whitespace: bool = True,
    case_sensitive: bool = True,
) -> str | None:
    """Normalize a join key without changing identifier case by default."""

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
    """Parse only an unambiguous, finite numeric expression."""

    if is_null(value) or _is_non_finite_numeric(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, Integral):
        return Decimal(int(value))
    if isinstance(value, Real):
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
        return parsed if parsed.is_finite() else None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text or not _NUMBER_RE.fullmatch(text):
        return None
    try:
        parsed = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def parse_datetime(value: Any) -> pd.Timestamp | None:
    """Parse an unambiguous date/time without inventing a timezone."""

    if is_null(value):
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value
    if isinstance(value, datetime):
        return pd.Timestamp(value)
    if isinstance(value, date):
        return pd.Timestamp(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    match = _DATE_RE.fullmatch(text)
    if not match or text[4] != text[7]:
        return None
    try:
        result = pd.Timestamp(text.replace("/", "-"))
    except (TypeError, ValueError, OverflowError):
        return None
    return None if pd.isna(result) else result


def _validate_tolerance(tolerance: Any) -> Decimal | None:
    if tolerance is None:
        return None
    if isinstance(tolerance, bool):
        raise ValueError("tolerance must be a finite non-negative number")
    try:
        decimal_tolerance = Decimal(str(tolerance))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("tolerance must be a finite non-negative number") from None
    if not decimal_tolerance.is_finite() or decimal_tolerance < 0:
        raise ValueError("tolerance must be a finite non-negative number")
    return decimal_tolerance


def _numeric_null(value: Any) -> bool:
    return is_null(value) and not _is_non_finite_numeric(value)


def _datetime_null(value: Any) -> bool:
    # A literal "NaN" in a date column is an invalid date token, not evidence
    # that both sides contain a legitimate null date.
    if isinstance(value, str) and value.strip().lower() == "nan":
        return False
    return is_null(value)


def normalize_value(value: Any, *, rule_type: str = "string", normalizers: list[str] | None = None) -> Any:
    normalizers = normalizers or []
    if is_null(value) and not (rule_type in {"number", "amount", "numeric"} and _is_non_finite_numeric(value)):
        return None
    if rule_type in {"number", "amount", "numeric"} or "numeric_parse" in normalizers:
        parsed = parse_number(value)
        if parsed is None:
            return None
        value = parsed
    elif rule_type == "datetime" or "datetime_parse" in normalizers:
        parsed_dt = parse_datetime(value)
        if parsed_dt is None:
            return None
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


def compare_values(
    left: Any,
    right: Any,
    rule_type: str,
    tolerance: Any,
    normalizers: list[str],
) -> ValueComparison:
    """Return a three-state, auditable comparison outcome."""

    decimal_tolerance = _validate_tolerance(tolerance)
    is_numeric = rule_type in {"number", "amount", "numeric"}
    left_null = _numeric_null(left) if is_numeric else (_datetime_null(left) if rule_type == "datetime" else is_null(left))
    right_null = _numeric_null(right) if is_numeric else (_datetime_null(right) if rule_type == "datetime" else is_null(right))

    if is_numeric and (_is_non_finite_numeric(left) or _is_non_finite_numeric(right)):
        return ValueComparison(
            status=ComparisonStatus.UNVERIFIED,
            difference_type="UNVERIFIED_NON_FINITE",
            reason_code="NON_FINITE_NUMERIC",
        )
    if is_numeric:
        left_number = None if left_null else parse_number(left)
        right_number = None if right_null else parse_number(right)
        if (not left_null and left_number is None) or (not right_null and right_number is None):
            return ValueComparison(
                status=ComparisonStatus.UNVERIFIED,
                difference_type="UNVERIFIED_NUMERIC_PARSE",
                reason_code="NUMERIC_PARSE_FAILED",
            )
    else:
        left_number = right_number = None
    if rule_type == "datetime":
        left_dt = None if left_null else parse_datetime(left)
        right_dt = None if right_null else parse_datetime(right)
        if (not left_null and left_dt is None) or (not right_null and right_dt is None):
            return ValueComparison(
                status=ComparisonStatus.UNVERIFIED,
                difference_type="UNVERIFIED_DATETIME_PARSE",
                reason_code="DATETIME_PARSE_FAILED",
            )
    else:
        left_dt = right_dt = None
    if left_null and right_null:
        return ValueComparison(status=ComparisonStatus.MATCH, difference_type="MATCH")
    if left_null or right_null:
        return ValueComparison(status=ComparisonStatus.MISMATCH, difference_type="NULL_MISMATCH")

    if is_numeric:
        assert left_number is not None and right_number is not None
        difference = abs(left_number - right_number)
        if difference == 0:
            return ValueComparison(
                status=ComparisonStatus.MATCH,
                difference_type="MATCH",
                normalized_left=left_number,
                normalized_right=right_number,
            )
        if decimal_tolerance is not None and difference <= decimal_tolerance:
            return ValueComparison(
                status=ComparisonStatus.MATCH,
                difference_type="MATCH_WITHIN_TOLERANCE",
                normalized_left=left_number,
                normalized_right=right_number,
            )
        return ValueComparison(
            status=ComparisonStatus.MISMATCH,
            difference_type="NUMERIC_TOLERANCE_MISMATCH",
            normalized_left=left_number,
            normalized_right=right_number,
        )

    if rule_type == "datetime":
        assert left_dt is not None and right_dt is not None
        left_aware = left_dt.tzinfo is not None
        right_aware = right_dt.tzinfo is not None
        if left_aware != right_aware:
            return ValueComparison(
                status=ComparisonStatus.UNVERIFIED,
                difference_type="UNVERIFIED_TIMEZONE_MISSING",
                reason_code="MIXED_TIMEZONE_AWARENESS",
            )
        if left_aware and right_aware:
            left_compare, right_compare = left_dt.tz_convert("UTC"), right_dt.tz_convert("UTC")
        else:
            left_compare, right_compare = left_dt, right_dt
        if left_compare == right_compare:
            return ValueComparison(
                status=ComparisonStatus.MATCH,
                difference_type="MATCH",
                normalized_left=left_compare.isoformat(),
                normalized_right=right_compare.isoformat(),
            )
        return ValueComparison(
            status=ComparisonStatus.MISMATCH,
            difference_type="DATETIME_MISMATCH",
            normalized_left=left_compare.isoformat(),
            normalized_right=right_compare.isoformat(),
        )

    left_normalized = normalize_value(left, rule_type=rule_type, normalizers=normalizers)
    right_normalized = normalize_value(right, rule_type=rule_type, normalizers=normalizers)
    if left_normalized == right_normalized:
        return ValueComparison(
            status=ComparisonStatus.MATCH,
            difference_type="FORMAT_ONLY_DIFFERENCE" if str(left) != str(right) else "MATCH",
            normalized_left=left_normalized,
            normalized_right=right_normalized,
        )
    if rule_type == "enum":
        return ValueComparison(
            status=ComparisonStatus.MISMATCH,
            difference_type="ENUM_MAPPING_REQUIRED",
            normalized_left=left_normalized,
            normalized_right=right_normalized,
        )
    return ValueComparison(
        status=ComparisonStatus.MISMATCH,
        difference_type="VALUE_MISMATCH",
        normalized_left=left_normalized,
        normalized_right=right_normalized,
    )


def values_equal(left: Any, right: Any, rule_type: str, tolerance: float | None, normalizers: list[str]) -> tuple[bool, str]:
    """Backward-compatible adapter for the old tuple API."""

    outcome = compare_values(left, right, rule_type, tolerance, normalizers)
    return outcome.status == ComparisonStatus.MATCH, outcome.difference_type
