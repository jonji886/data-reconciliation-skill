from pathlib import Path
import json

import pandas as pd
from typer.testing import CliRunner

from reconcile_skill.loaders import LoadedTable
from reconcile_skill.mapping import infer_manual_mapping_type
from reconcile_skill.models import CompareRule
from reconcile_skill.profiler import profile_dataframe
from reconcile_skill.reconciler import reconcile
from reconcile_skill.report import write_report
from reconcile_skill.config import load_mapping_yaml
from reconcile_skill.cli import app
from reconcile_skill.key_detector import detect_key_candidates


def test_identifier_keys_are_case_sensitive_by_default():
    source = pd.DataFrame({"SKU": ["ABC001"]})
    target = pd.DataFrame({"SKU": ["abc001"]})

    result = reconcile(source, target, source_key="SKU", target_key="SKU", rules=[])

    assert result.summary.matched_unique_key_count == 0
    assert result.summary.missing_target_key_count == 1
    assert result.summary.missing_source_key_count == 1
    assert result.summary.missing_target_row_count == 1
    assert result.summary.missing_source_row_count == 1


def test_case_distinct_identifiers_are_not_duplicates():
    frame = pd.DataFrame({"SKU": ["ABC001", "abc001"]})

    result = reconcile(frame, frame.copy(), source_key="SKU", target_key="SKU", rules=[])

    assert result.summary.duplicate_source_key_count == 0
    assert result.summary.duplicate_target_key_count == 0
    assert result.summary.matched_unique_key_count == 2


def test_explicit_case_insensitive_key_configuration_matches():
    source = pd.DataFrame({"SKU": ["ABC001"]})
    target = pd.DataFrame({"SKU": ["abc001"]})

    result = reconcile(
        source,
        target,
        source_key="SKU",
        target_key="SKU",
        rules=[],
        case_sensitive=False,
    )

    assert result.summary.matched_unique_key_count == 1
    assert result.summary.missing_source_row_count == 0
    assert result.summary.missing_target_row_count == 0


def test_key_detection_uses_explicit_case_sensitivity():
    source = LoadedTable(pd.DataFrame({"SKU": ["ABC001"]}), "source.csv", None)
    target = LoadedTable(pd.DataFrame({"sku": ["abc001"]}), "target.csv", None)

    case_sensitive = detect_key_candidates(
        profile_dataframe(source),
        profile_dataframe(target),
        source.dataframe,
        target.dataframe,
    )
    case_insensitive = detect_key_candidates(
        profile_dataframe(source),
        profile_dataframe(target),
        source.dataframe,
        target.dataframe,
        case_sensitive=False,
    )

    assert case_insensitive[0].score > case_sensitive[0].score


def test_manual_mapping_type_is_inferred_from_profiles():
    source = LoadedTable(pd.DataFrame({"订单金额": [100, 200], "订单状态": ["paid", "cancelled"]}), "source.csv", None)
    target = LoadedTable(pd.DataFrame({"total_amount": [100, 200], "status": ["SUCCESS", "CLOSED"]}), "target.csv", None)
    source_profile = profile_dataframe(source)
    target_profile = profile_dataframe(target)

    assert infer_manual_mapping_type(source_profile, target_profile, "订单金额", "total_amount") == "numeric"
    assert infer_manual_mapping_type(source_profile, target_profile, "订单状态", "status") == "enum"


def test_manual_mapping_types_cover_datetime_and_identifier():
    source = LoadedTable(
        pd.DataFrame({"创建时间": ["2026-01-01"], "商品编码": ["ABC001"]}),
        "source.csv",
        None,
    )
    target = LoadedTable(
        pd.DataFrame({"created_at": ["2026-01-01"], "sku": ["ABC001"]}),
        "target.csv",
        None,
    )
    source_profile = profile_dataframe(source)
    target_profile = profile_dataframe(target)

    assert infer_manual_mapping_type(source_profile, target_profile, "创建时间", "created_at") == "datetime"
    assert infer_manual_mapping_type(source_profile, target_profile, "商品编码", "sku") == "identifier"


def test_case_sensitive_mapping_yaml_is_reusable(tmp_path: Path):
    result = reconcile(
        pd.DataFrame({"SKU": ["ABC001"]}),
        pd.DataFrame({"SKU": ["abc001"]}),
        source_key="SKU",
        target_key="SKU",
        rules=[],
        case_sensitive=False,
    )
    _, mapping_path = write_report(
        result,
        tmp_path,
        source_key="SKU",
        target_key="SKU",
        key_case_sensitive=False,
    )

    spec = load_mapping_yaml(mapping_path)

    assert spec.key["case_sensitive"] is False


def test_summary_distinguishes_keys_from_rows():
    source = pd.DataFrame({"id": ["A001", "A001", "A002"]})
    target = pd.DataFrame({"id": ["A001", "A002", "A003"]})
    result = reconcile(source, target, source_key="id", target_key="id", rules=[])

    assert result.summary.duplicate_source_key_count == 1
    assert result.summary.duplicate_source_row_count == 2
    assert result.summary.missing_source_key_count == 1
    assert result.summary.missing_source_row_count == 1


def test_cli_reuses_explicit_case_insensitive_key_rule(tmp_path: Path):
    source = tmp_path / "source.csv"
    target = tmp_path / "target.csv"
    mapping = tmp_path / "mapping.yaml"
    source.write_text("SKU\nABC001\n", encoding="utf-8")
    target.write_text("SKU\nabc001\n", encoding="utf-8")
    mapping.write_text(
        "version: 1\nkey:\n  source: SKU\n  target: SKU\n  case_sensitive: false\nfields: []\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"

    result = CliRunner().invoke(
        app,
        [
            "--source", str(source),
            "--target", str(target),
            "--mapping", str(mapping),
            "--output", str(output),
            "--non-interactive",
        ],
    )

    assert result.exit_code == 0, result.stdout
    summary = json.loads((output / "run_log.json").read_text(encoding="utf-8"))["summary"]
    assert summary["matched_unique_key_count"] == 1
    assert summary["missing_source_row_count"] == 0
    assert summary["missing_target_row_count"] == 0
