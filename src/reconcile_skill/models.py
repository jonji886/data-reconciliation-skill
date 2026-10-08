"""Stable data contracts for profiling, mapping and reconciliation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ComparisonStatus(str, Enum):
    """Outcome of a value comparison.

    ``UNVERIFIED`` is intentionally separate from ``MISMATCH``: the former
    means the engine could not establish a reliable comparison and must never
    be presented as a confirmed equality.
    """

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNVERIFIED = "UNVERIFIED"


class ValueComparison(BaseModel):
    status: ComparisonStatus
    difference_type: str
    normalized_left: Any | None = None
    normalized_right: Any | None = None
    reason_code: str | None = None


class ColumnProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    dtype: str
    null_count: int = 0
    null_ratio: float = 0.0
    unique_count: int = 0
    unique_ratio: float = 0.0
    top_values: list[Any] = Field(default_factory=list)
    sample_values: list[Any] = Field(default_factory=list)
    min: Any | None = None
    max: Any | None = None
    max_length: int | None = None
    inferred_semantic_type: str | None = None


class KeyCandidate(BaseModel):
    """A paired source/target key recommendation."""

    columns: list[str]
    source_column: str | None = None
    target_column: str | None = None
    score: float
    reasons: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False


class TableProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    file_name: str
    sheet_name: str | None = None
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    candidate_keys: list[KeyCandidate] = Field(default_factory=list)


class MappingSuggestion(BaseModel):
    source_column: str
    target_column: str | None = None
    confidence: float
    mapping_type: str
    reasons: list[str] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    requires_confirmation: bool = False


class CompareRule(BaseModel):
    source_column: str
    target_column: str
    rule_type: str = "string"
    tolerance: float | None = None
    normalizers: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False

    @field_validator("tolerance")
    @classmethod
    def validate_tolerance(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isfinite(float(value)) or float(value) < 0:
            raise ValueError("tolerance must be a finite non-negative number")
        return value


class ReconciliationSummary(BaseModel):
    """Summary with explicit key-versus-row terminology.

    The legacy fields remain serialized for consumers of the MVP API. They are
    aliases populated by the engine and are intentionally omitted from the
    human-facing Summary worksheet.
    """

    source_row_count: int
    target_row_count: int
    matched_key_count: int
    matched_unique_key_count: int
    missing_source_key_count: int
    missing_source_row_count: int
    missing_target_key_count: int
    missing_target_row_count: int
    duplicate_source_key_count: int
    duplicate_source_row_count: int
    duplicate_target_key_count: int
    duplicate_target_row_count: int
    value_mismatch_count: int
    source_rows: int | None = None
    target_rows: int | None = None
    matched_rows: int | None = None
    missing_in_source: int | None = None
    missing_in_target: int | None = None
    duplicate_source_keys: int | None = None
    duplicate_target_keys: int | None = None
    value_mismatches: int | None = None
    matched_value_count: int = 0
    unverified_count: int = 0
    unverified_field_count: int = 0
    compared_field_count: int = 0
    unmapped_field_count: int = 0
    pending_field_count: int = 0
    skipped_field_count: int = 0
    unsupported_field_count: int = 0
    coverage_status: str = "PARTIAL_NEEDS_REVIEW"
    reconciliation_status: str = "PARTIAL_NEEDS_REVIEW"


class ReconciliationResult(BaseModel):
    summary: ReconciliationSummary
    mapping: list[CompareRule]
    missing_in_source: list[dict[str, Any]] = Field(default_factory=list)
    missing_in_target: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_source: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_target: list[dict[str, Any]] = Field(default_factory=list)
    value_mismatch: list[dict[str, Any]] = Field(default_factory=list)
    unverified: list[dict[str, Any]] = Field(default_factory=list)
    field_coverage: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: str = "PARTIAL_NEEDS_REVIEW"
    run_id: str = ""
    run_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MappingSpec(BaseModel):
    version: int = 1
    key: dict[str, str | bool]
    fields: list[CompareRule]
