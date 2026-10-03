"""Typer command-line entry point."""

from __future__ import annotations

from pathlib import Path
import time

import typer

from .config import load_mapping_yaml
from .errors import ReconciliationError
from .key_detector import detect_key_candidates
from .loaders import load_table
from .logging_utils import write_run_log
from .mapping import rules_from_suggestions
from .models import KeyCandidate
from .profiler import profile_dataframe
from .reconciler import reconcile
from .report import write_report
from .semantic_matcher import suggest_column_mappings

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Excel / CSV 智能对账与差异定位")


def _choose_key(
    candidates: list[KeyCandidate],
    *,
    source_columns: list[str],
    target_columns: list[str],
    non_interactive: bool,
) -> KeyCandidate:
    typer.echo("候选主键:")
    for index, candidate in enumerate(candidates[:3], 1):
        typer.echo(f"  {index}. {candidate.source_column} ↔ {candidate.target_column} confidence={candidate.score:.2f}")
    typer.echo("选择: [1-3] 候选  [M] 手动指定  [A] 退出")
    if non_interactive:
        selected = candidates[0]
        if selected.requires_confirmation:
            raise ReconciliationError("AMBIGUOUS_MAPPING", "最高分主键置信度不足，非交互模式不会静默选择。")
        return selected
    while True:
        answer = typer.prompt("请选择主键").strip()
        if answer.upper() == "A":
            raise ReconciliationError("ABORTED", "用户取消了对账。")
        if answer.upper() == "M":
            source_key = typer.prompt("Source key").strip()
            target_key = typer.prompt("Target key").strip()
            if source_key not in source_columns or target_key not in target_columns:
                typer.echo("字段不存在，请重新输入。")
                continue
            return KeyCandidate(
                columns=[source_key, target_key],
                source_column=source_key,
                target_column=target_key,
                score=1.0,
                reasons=["用户手动指定并确认"],
            )
        if answer.isdigit() and 1 <= int(answer) <= min(3, len(candidates)):
            return candidates[int(answer) - 1]
        typer.echo("请输入 1-3、M 或 A。")


def _choose_mapping(suggestion, *, target_columns: list[str], non_interactive: bool):
    if suggestion.target_column is None:
        typer.echo(f"没有达到自动映射阈值: {suggestion.source_column}")
        if non_interactive:
            return None
        typer.echo("选择: [S] 跳过  [M] 手动指定 Target")
        while True:
            answer = typer.prompt("请选择 Mapping").strip().upper()
            if answer == "S":
                return None
            if answer == "M":
                target = typer.prompt("Manual target").strip()
                if target not in target_columns:
                    typer.echo("Target 字段不存在，请重新输入。")
                    continue
                return suggestion.model_copy(
                    update={"target_column": target, "mapping_type": "string", "requires_confirmation": False}
                )
            typer.echo("请输入 S 或 M。")
    if not suggestion.requires_confirmation:
        return suggestion
    typer.echo(f"Source column: {suggestion.source_column}")
    typer.echo("Candidate mappings:")
    candidates = suggestion.candidates or [{"target_column": suggestion.target_column, "confidence": suggestion.confidence}]
    for index, candidate in enumerate(candidates, 1):
        typer.echo(f"  {index}. {candidate['target_column']} {candidate.get('confidence', 0):.2f}")
    typer.echo("选择: [1-n] 选择候选  [S] 跳过  [M] 手动指定 Target")
    if non_interactive:
        raise ReconciliationError(
            "AMBIGUOUS_MAPPING",
            f"Mapping 未确认，非交互模式不会静默执行: {suggestion.source_column} -> {suggestion.target_column}",
        )
    while True:
        answer = typer.prompt("请选择 Mapping").strip()
        if answer.upper() == "S":
            return None
        if answer.upper() == "M":
            target = typer.prompt("Manual target").strip()
            if target not in target_columns:
                typer.echo("Target 字段不存在，请重新输入。")
                continue
            return suggestion.model_copy(update={"target_column": target, "requires_confirmation": False})
        if answer.isdigit() and 1 <= int(answer) <= len(candidates):
            candidate = candidates[int(answer) - 1]
            target = candidate["target_column"]
            return suggestion.model_copy(
                update={
                    "target_column": target,
                    "mapping_type": candidate.get("mapping_type", suggestion.mapping_type),
                    "requires_confirmation": False,
                }
            )
        typer.echo("请输入候选编号、S 或 M。")


@app.command()
def reconcile_command(
    source: Path = typer.Option(..., "--source", exists=True, readable=True),
    target: Path = typer.Option(..., "--target", exists=True, readable=True),
    output: Path = typer.Option(Path("outputs/run_001"), "--output"),
    source_sheet: str | None = typer.Option(None, "--source-sheet"),
    target_sheet: str | None = typer.Option(None, "--target-sheet"),
    mapping: Path | None = typer.Option(None, "--mapping", exists=True, readable=True),
    tolerance: float | None = typer.Option(0.01, "--tolerance"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="遇到需要确认的规则时直接失败"),
):
    """Load two files, propose/confirm rules, reconcile, and export evidence."""

    started_at = time.perf_counter()
    try:
        source_table = load_table(source, sheet_name=source_sheet)
        target_table = load_table(target, sheet_name=target_sheet)
        source_profile = profile_dataframe(source_table)
        target_profile = profile_dataframe(target_table)
        candidates = detect_key_candidates(source_profile, target_profile, source_table.dataframe, target_table.dataframe)
        source_profile.candidate_keys = candidates
        target_profile.candidate_keys = candidates
        if not candidates and mapping is None:
            raise ReconciliationError("KEY_NOT_FOUND", "没有找到可用的跨表主键候选。")
        typer.echo(f"Source: {source_table.file_name} rows={source_profile.row_count} columns={source_profile.column_count}")
        typer.echo(f"Target: {target_table.file_name} rows={target_profile.row_count} columns={target_profile.column_count}")
        if mapping is not None:
            saved_spec = load_mapping_yaml(mapping)
            source_key = saved_spec.key.get("source", "")
            target_key = saved_spec.key.get("target", "")
            if not source_key or not target_key:
                raise ReconciliationError("SCHEMA_ERROR", "Mapping YAML 缺少 key.source 或 key.target。")
            selected = KeyCandidate(
                columns=[source_key, target_key],
                source_column=source_key,
                target_column=target_key,
                score=1.0,
                reasons=["来自已保存且已确认的 Mapping YAML"],
            )
            suggestions = []
            rules = saved_spec.fields
            typer.echo(f"使用已保存 Mapping: {source_key} ↔ {target_key}")
        else:
            selected = _choose_key(
                candidates,
                source_columns=list(source_table.dataframe.columns),
                target_columns=list(target_table.dataframe.columns),
                non_interactive=non_interactive,
            )
            typer.echo(f"使用主键: {selected.source_column} ↔ {selected.target_column} (confidence={selected.score:.2f})")

            suggestions = suggest_column_mappings(source_profile, target_profile, source_table.dataframe, target_table.dataframe)
            confirmed: set[str] = set()
            selected_suggestions = []
            for suggestion in suggestions:
                typer.echo(f"Mapping: {suggestion.source_column} -> {suggestion.target_column} confidence={suggestion.confidence:.2f} type={suggestion.mapping_type}")
                chosen = _choose_mapping(
                    suggestion,
                    target_columns=list(target_table.dataframe.columns),
                    non_interactive=non_interactive,
                )
                if chosen is not None:
                    selected_suggestions.append(chosen)
                    confirmed.add(chosen.source_column)
            suggestions = selected_suggestions
            rules = rules_from_suggestions(suggestions, confirmed_columns=confirmed, numeric_tolerance=tolerance)
        result = reconcile(
            source_table.dataframe,
            target_table.dataframe,
            source_key=selected.source_column or "",
            target_key=selected.target_column or "",
            rules=rules,
        )
        report_path, mapping_path = write_report(
            result,
            output,
            source_key=selected.source_column or "",
            target_key=selected.target_column or "",
            source_file=source_table.file_name,
            target_file=target_table.file_name,
            mapping_suggestions=[item.model_dump() for item in suggestions] if suggestions else [item.model_dump() for item in rules],
        )
        log_path = write_run_log(
            output,
            source_path=source,
            target_path=target,
            source_key=selected.source_column or "",
            target_key=selected.target_column or "",
            result=result,
            started_at=started_at,
        )
        typer.echo(f"完成: {report_path}")
        typer.echo(f"Mapping: {mapping_path}")
        typer.echo(f"Run log: {log_path}")
        typer.echo(result.summary.model_dump_json())
    except ReconciliationError as exc:
        typer.echo(f"[{exc.code}] {exc.message}", err=True)
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
