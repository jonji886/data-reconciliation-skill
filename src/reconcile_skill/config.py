"""Run configuration and saved mapping loading."""

from __future__ import annotations

from pathlib import Path

import yaml

from .errors import ReconciliationError
from .models import CompareRule, MappingSpec


def load_mapping_yaml(path: str | Path) -> MappingSpec:
    try:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("根节点必须是对象")
        normalized_fields = []
        for field in payload.get("fields", []):
            if not isinstance(field, dict):
                raise ValueError("fields 中每个元素必须是对象")
            normalized_fields.append(
                {
                    "source_column": field.get("source", field.get("source_column")),
                    "target_column": field.get("target", field.get("target_column")),
                    "rule_type": field.get("rule", field.get("rule_type", "string")),
                    "tolerance": field.get("tolerance"),
                    "normalizers": field.get("normalizers", []),
                    "requires_confirmation": field.get("requires_confirmation", False),
                }
            )
        payload["fields"] = normalized_fields
        return MappingSpec.model_validate(payload)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ReconciliationError("SCHEMA_ERROR", f"Mapping YAML 无法读取: {path}: {exc}") from exc
