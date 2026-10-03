"""Explainable candidate key detection."""

from __future__ import annotations

import re

import pandas as pd

from .models import KeyCandidate, TableProfile
from .normalizers import normalize_key


def _name_score(source: str, target: str) -> float:
    aliases = {
        "identifier": "id",
        "number": "id",
        "num": "id",
        "no": "id",
        "client": "customer",
        "customer": "customer",
        "member": "user",
        "user": "user",
        "编号": "id",
        "编码": "code",
        "订单号": "order_no",
    }

    def clean(value: str) -> str:
        value = re.sub(r"[^a-z0-9\u4e00-\u9fff]", " ", value.lower())
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", value)
        return " ".join(aliases.get(token, token) for token in tokens)

    left, right = clean(source), clean(target)
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.82
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    return len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)


def _compatibility(source_dtype: str, target_dtype: str) -> float:
    numeric = lambda value: any(token in value.lower() for token in ("int", "float", "decimal", "number"))
    if numeric(source_dtype) == numeric(target_dtype):
        return 1.0
    return 0.35


def _overlap(source: pd.Series, target: pd.Series) -> float:
    left = {normalize_key(value) for value in source if normalize_key(value) is not None}
    right = {normalize_key(value) for value in target if normalize_key(value) is not None}
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def detect_key_candidates(
    source_profile: TableProfile,
    target_profile: TableProfile,
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    *,
    limit: int = 10,
) -> list[KeyCandidate]:
    candidates: list[KeyCandidate] = []
    for source in source_profile.columns:
        for target in target_profile.columns:
            source_unique = source.unique_ratio if source.null_count < source_profile.row_count else 0.0
            target_unique = target.unique_ratio if target.null_count < target_profile.row_count else 0.0
            overlap = _overlap(source_df[source.name], target_df[target.name])
            name = _name_score(source.name, target.name)
            dtype = _compatibility(source.dtype, target.dtype)
            non_null = (1 - source.null_ratio + 1 - target.null_ratio) / 2
            score = 0.33 * min(source_unique, target_unique) + 0.20 * non_null + 0.22 * name + 0.20 * overlap + 0.05 * dtype
            score = round(min(max(score, 0.0), 1.0), 4)
            reasons = [
                f"唯一率 source={source_unique:.1%}, target={target_unique:.1%}",
                f"非空率 source={1 - source.null_ratio:.1%}, target={1 - target.null_ratio:.1%}",
                f"跨表值交集覆盖率 {overlap:.1%}",
            ]
            if name >= 0.8:
                reasons.append("字段名称具有 ID/code/no 等主键语义或高度相似")
            if min(source_unique, target_unique) < 0.95:
                reasons.append("唯一率不足，不能直接视为安全主键")
            candidates.append(
                KeyCandidate(
                    columns=[source.name, target.name],
                    source_column=source.name,
                    target_column=target.name,
                    score=score,
                    reasons=reasons,
                    requires_confirmation=score < 0.95,
                )
            )
    candidates.sort(key=lambda item: (-item.score, item.source_column or "", item.target_column or ""))
    return candidates[:limit]
