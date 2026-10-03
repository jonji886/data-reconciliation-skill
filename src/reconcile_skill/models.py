"""Stable data contracts for profiling, mapping and reconciliation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class ReconciliationSummary(BaseModel):
    source_rows: int
    target_rows: int
    matched_rows: int
    missing_in_source: int
    missing_in_target: int
    duplicate_source_keys: int
    duplicate_target_keys: int
    value_mismatches: int


class ReconciliationResult(BaseModel):
    summary: ReconciliationSummary
    mapping: list[CompareRule]
    missing_in_source: list[dict[str, Any]] = Field(default_factory=list)
    missing_in_target: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_source: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_target: list[dict[str, Any]] = Field(default_factory=list)
    value_mismatch: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    run_id: str = ""
    run_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MappingSpec(BaseModel):
    version: int = 1
    key: dict[str, str]
    fields: list[CompareRule]
