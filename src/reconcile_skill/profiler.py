"""Deterministic table and field profiling."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from .loaders import LoadedTable
from .models import ColumnProfile, TableProfile

_ID_WORDS = {"id", "code", "no", "number", "编号", "编码", "订单号", "客户号", "用户号"}
_STATUS_WORDS = {"status", "state", "type", "category", "状态", "类型", "分类"}
_DATE_WORDS = {"date", "time", "at", "日期", "时间", "创建", "更新"}
_AMOUNT_WORDS = {"amount", "price", "total", "fee", "cost", "金额", "价格", "费用", "总额"}
_NAME_WORDS = {"name", "姓名", "名称", "客户名", "用户名"}


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().upper() in {"", "NULL", "N/A", "NA", "NONE", "NAN"}:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _json_value(value: Any) -> Any:
    if _is_null(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def _tokens(name: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9\\s]", name) if token.strip()}


def infer_semantic_type(name: str, series: pd.Series) -> str:
    tokens = _tokens(name)
    lowered = name.lower()
    non_null = series[~series.map(_is_null)]
    if tokens & _DATE_WORDS or "datetime" in lowered:
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed") if len(non_null) else pd.Series(dtype=object)
        if len(non_null) and parsed.notna().mean() >= 0.8:
            return "datetime"
    if tokens & _AMOUNT_WORDS:
        numeric = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce")
        if len(non_null) and numeric.notna().mean() >= 0.8:
            return "amount"
    if tokens & _ID_WORDS:
        return "identifier"
    if tokens & _STATUS_WORDS:
        return "enum"
    if tokens & _NAME_WORDS:
        return "name"
    if pd.api.types.is_numeric_dtype(series):
        return "number"
    if len(non_null):
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.8:
            return "datetime"
    return "string"


def profile_dataframe(table: LoadedTable) -> TableProfile:
    df = table.dataframe
    columns: list[ColumnProfile] = []
    row_count = len(df)
    for name in df.columns:
        series = df[name]
        null_mask = series.map(_is_null)
        non_null = series[~null_mask]
        unique_values = {_json_value(value) for value in non_null}
        values = [_json_value(value) for value in non_null]
        top = series[~null_mask].map(_json_value).value_counts(dropna=False).head(5)
        top_values = [{"value": _json_value(index), "count": int(count)} for index, count in top.items()]
        minimum = maximum = None
        if len(non_null):
            if pd.api.types.is_numeric_dtype(series):
                numeric = pd.to_numeric(non_null, errors="coerce").dropna()
                if len(numeric):
                    minimum, maximum = _json_value(numeric.min()), _json_value(numeric.max())
            else:
                parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
                if len(parsed) and parsed.notna().mean() >= 0.8:
                    minimum, maximum = _json_value(parsed.min()), _json_value(parsed.max())
        lengths = [len(str(value)) for value in values if value is not None]
        columns.append(
            ColumnProfile(
                name=str(name),
                dtype=str(series.dtype),
                null_count=int(null_mask.sum()),
                null_ratio=float(null_mask.mean()) if row_count else 0.0,
                unique_count=len(unique_values),
                unique_ratio=(len(unique_values) / len(non_null)) if len(non_null) else 0.0,
                top_values=top_values,
                sample_values=values[:10],
                min=minimum,
                max=maximum,
                max_length=max(lengths) if lengths else None,
                inferred_semantic_type=infer_semantic_type(str(name), series),
            )
        )
    return TableProfile(
        file_name=table.file_name,
        sheet_name=table.sheet_name,
        row_count=row_count,
        column_count=len(df.columns),
        columns=columns,
    )
