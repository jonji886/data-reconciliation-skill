"""Local heuristic matcher; no LLM or raw-file upload required."""

from __future__ import annotations

import re
from typing import Protocol

import pandas as pd

from .models import ColumnProfile, MappingSuggestion, TableProfile


class SemanticMatcher(Protocol):
    """Optional semantic matching boundary; implementations must not compute diffs."""

    def propose_column_mapping(
        self,
        source_profile: TableProfile,
        target_profile: TableProfile,
        source_df: pd.DataFrame,
        target_df: pd.DataFrame,
    ) -> list[MappingSuggestion]:
        ...


class HeuristicMatcher:
    """Default offline matcher used when no LLM is configured."""

    def propose_column_mapping(
        self,
        source_profile: TableProfile,
        target_profile: TableProfile,
        source_df: pd.DataFrame,
        target_df: pd.DataFrame,
    ) -> list[MappingSuggestion]:
        return suggest_column_mappings(source_profile, target_profile, source_df, target_df)

SYNONYMS = {
    "id": {"id", "identifier", "no", "num", "number", "编号", "号码", "号"},
    "code": {"code", "编码", "代码"},
    "order": {"order", "订单", "单据"},
    "customer": {"customer", "client", "客户"},
    "user": {"user", "member", "用户", "会员"},
    "product": {"product", "商品"},
    "amount": {"amount", "total", "money", "price", "金额", "总额", "费用", "支付"},
    "paid": {"paid", "实付", "付款"},
    "status": {"status", "state", "阶段", "状态"},
    "name": {"name", "名称", "姓名"},
    "phone": {"phone", "mobile", "telephone", "手机号", "手机号码"},
    "created": {"created", "create", "创建"},
    "updated": {"updated", "update", "更新"},
    "time": {"time", "at", "date", "日期", "时间"},
}

_PHRASE_ALIASES = {
    "订单编号": "order id",
    "订单号": "order id",
    "订单id": "order id",
    "客户编号": "customer id",
    "客户号": "customer id",
    "客户名称": "customer name",
    "客户姓名": "customer name",
    "手机号码": "phone",
    "手机号": "phone",
    "订单金额": "order amount",
    "支付金额": "paid amount",
    "实付金额": "paid amount",
    "订单状态": "order status",
    "创建时间": "created time",
    "更新时间": "updated time",
    "商品编码": "product code",
}
_SPECIAL_TOKEN_EXPANSIONS = {"sku": {"product", "code"}}


def semantic_tokens(name: str) -> set[str]:
    """Tokenize English and Chinese business phrases into semantic concepts."""

    normalized = re.sub(r"[\s_\-/]+", " ", str(name).strip().lower())
    for phrase, replacement in sorted(_PHRASE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = normalized.replace(phrase, f" {replacement} ")
    raw = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", normalized)
    expanded: set[str] = set()
    for token in raw:
        if token in _SPECIAL_TOKEN_EXPANSIONS:
            expanded.update(_SPECIAL_TOKEN_EXPANSIONS[token])
            continue
        expanded.add(token)
        for canonical, values in SYNONYMS.items():
            if token in values:
                expanded.add(canonical)
    return expanded


def _tokens(name: str) -> set[str]:
    return semantic_tokens(name)


def _name_similarity(source: str, target: str) -> tuple[float, str]:
    left_tokens, right_tokens = _tokens(source), _tokens(target)
    if left_tokens == right_tokens:
        return 1.0, "字段名完全一致"
    if left_tokens <= right_tokens or right_tokens <= left_tokens:
        return 0.88, "字段名存在包含关系"
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    return overlap, f"字段语义 token 重叠率 {overlap:.1%}"


def _dtype_compatible(source: ColumnProfile, target: ColumnProfile) -> tuple[float, str]:
    left, right = source.inferred_semantic_type, target.inferred_semantic_type
    if left == right:
        return 1.0, f"两列推断类型均为 {left}"
    numeric = {"number", "amount"}
    if left in numeric and right in numeric:
        return 0.85, "两列均为数值类"
    if {left, right} <= {"string", "identifier"}:
        return 0.7, "两列均可作为字符串/标识符比较"
    return 0.2, f"类型兼容性较弱 ({left} vs {right})"


def _sample_overlap(source_df: pd.DataFrame, target_df: pd.DataFrame, left: str, right: str) -> float:
    def clean(value: object) -> str:
        return str(value).strip().lower()

    source_values = {clean(value) for value in source_df[left].dropna().head(100) if str(value).strip()}
    target_values = {clean(value) for value in target_df[right].dropna().head(100) if str(value).strip()}
    if not source_values or not target_values:
        return 0.0
    return len(source_values & target_values) / min(len(source_values), len(target_values))


def _mapping_type(source: ColumnProfile, target: ColumnProfile) -> str:
    semantic = source.inferred_semantic_type or target.inferred_semantic_type
    if semantic in {"amount", "number"}:
        return "numeric"
    if semantic == "datetime":
        return "datetime"
    if semantic == "enum":
        return "enum"
    return "string"


def suggest_column_mappings(
    source_profile: TableProfile,
    target_profile: TableProfile,
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    *,
    minimum_confidence: float = 0.45,
) -> list[MappingSuggestion]:
    suggestions: list[MappingSuggestion] = []
    for source in source_profile.columns:
        scored: list[tuple[float, ColumnProfile, list[str], str]] = []
        for target in target_profile.columns:
            name_score, name_reason = _name_similarity(source.name, target.name)
            dtype_score, dtype_reason = _dtype_compatible(source, target)
            sample_overlap = _sample_overlap(source_df, target_df, source.name, target.name)
            reasons = [name_reason, dtype_reason, f"样本值交集覆盖率 {sample_overlap:.1%}"]
            score = 0.55 * name_score + 0.20 * dtype_score + 0.25 * sample_overlap
            scored.append((score, target, reasons, _mapping_type(source, target)))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        candidate_rows = [
            {
                "target_column": target.name,
                "confidence": round(min(score, 1.0), 4),
                "mapping_type": mapping_type,
            }
            for score, target, _, mapping_type in scored[:3]
        ]
        if not scored or scored[0][0] < minimum_confidence:
            suggestions.append(
                MappingSuggestion(
                    source_column=source.name,
                    target_column=None,
                    confidence=round(scored[0][0], 4) if scored else 0.0,
                    mapping_type="unmapped",
                    reasons=["没有达到最低映射置信度"],
                    candidates=candidate_rows,
                    requires_confirmation=True,
                )
            )
            continue
        score, target, reasons, mapping_type = scored[0]
        if len(scored) > 1 and score - scored[1][0] < 0.08:
            reasons.append(f"与次优候选差距仅 {score - scored[1][0]:.1%}")
            score = min(score, 0.74)
        if mapping_type == "enum":
            reasons.append("枚举字段即使名称相同也默认需要人工确认")
        collision_sources = [
            existing.source_column for existing in suggestions if existing.target_column == target.name
        ]
        if collision_sources:
            reasons.append(f"MAPPING_COLLISION: target={target.name} 已被 {', '.join(collision_sources)} 选择")
        suggestions.append(
            MappingSuggestion(
                source_column=source.name,
                target_column=target.name,
                confidence=round(min(score, 1.0), 4),
                mapping_type=mapping_type,
                reasons=reasons,
                candidates=candidate_rows,
                requires_confirmation=(mapping_type == "enum" or score < 0.95 or bool(collision_sources)),
            )
        )
    target_sources: dict[str, list[str]] = {}
    for suggestion in suggestions:
        if suggestion.target_column is not None:
            target_sources.setdefault(suggestion.target_column, []).append(suggestion.source_column)
    for suggestion in suggestions:
        if suggestion.target_column and len(target_sources.get(suggestion.target_column, [])) > 1:
            if not any(reason.startswith("MAPPING_COLLISION:") for reason in suggestion.reasons):
                suggestion.reasons.append(
                    f"MAPPING_COLLISION: target={suggestion.target_column} 已被 {', '.join(target_sources[suggestion.target_column])} 选择"
                )
            suggestion.requires_confirmation = True
    return suggestions
