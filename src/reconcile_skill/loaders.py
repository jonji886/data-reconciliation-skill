"""CSV/XLSX loaders with explicit parse and sheet-selection errors."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .errors import ReconciliationError


@dataclass(frozen=True)
class LoadedTable:
    dataframe: pd.DataFrame
    file_name: str
    sheet_name: str | None
    available_sheets: tuple[str, ...] = ()


def _detect_delimiter(path: Path, encoding: str) -> str:
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            sample = handle.read(8192)
        if not sample.strip():
            return ","
        return csv.Sniffer().sniff(sample, delimiters=",;\\t|").delimiter
    except (OSError, UnicodeError, csv.Error):
        return ","


def _load_csv(path: Path) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            delimiter = _detect_delimiter(path, encoding)
            return pd.read_csv(path, encoding=encoding, sep=delimiter, dtype=object)
        except (UnicodeDecodeError, LookupError, pd.errors.ParserError, ValueError) as exc:
            errors.append(f"{encoding}: {exc}")
    raise ReconciliationError(
        "FILE_ERROR",
        f"无法解析 CSV 文件 {path.name}。请确认文件编码为 UTF-8 且格式完整。",
        details={"errors": errors},
    )


def load_table(path: str | Path, *, sheet_name: str | None = None) -> LoadedTable:
    """Load one CSV or one explicitly selected XLSX sheet."""

    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise ReconciliationError("FILE_ERROR", f"文件不存在或不是普通文件: {file_path}")
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".csv":
            dataframe = _load_csv(file_path)
            selected_sheet = None
            sheets: tuple[str, ...] = ()
        elif suffix in {".xlsx", ".xlsm"}:
            sheets = tuple(pd.ExcelFile(file_path).sheet_names)
            if not sheets:
                raise ReconciliationError("FILE_ERROR", f"Excel 文件没有可用 Sheet: {file_path.name}")
            if sheet_name is None and len(sheets) > 1:
                raise ReconciliationError(
                    "SCHEMA_ERROR",
                    f"Excel 文件包含多个 Sheet，请显式选择: {', '.join(sheets)}",
                    details={"available_sheets": sheets},
                )
            selected_sheet = sheet_name or sheets[0]
            if selected_sheet not in sheets:
                raise ReconciliationError(
                    "SCHEMA_ERROR",
                    f"Sheet 不存在: {selected_sheet}",
                    details={"available_sheets": sheets},
                )
            dataframe = pd.read_excel(file_path, sheet_name=selected_sheet, dtype=object)
        else:
            raise ReconciliationError("FILE_ERROR", f"不支持的文件类型: {suffix or '<无扩展名>'}")
    except ReconciliationError:
        raise
    except (OSError, ValueError, ImportError) as exc:
        raise ReconciliationError("FILE_ERROR", f"解析文件失败: {file_path.name}: {exc}") from exc

    if dataframe is None or len(dataframe.columns) == 0:
        raise ReconciliationError("SCHEMA_ERROR", f"文件没有表头字段: {file_path.name}")
    columns = [str(column).strip() for column in dataframe.columns]
    if any(not column for column in columns) or len(set(columns)) != len(columns):
        raise ReconciliationError("SCHEMA_ERROR", f"文件包含空字段名或重复字段名: {file_path.name}")
    dataframe = dataframe.copy()
    dataframe.columns = columns
    return LoadedTable(dataframe, file_path.name, selected_sheet, sheets)
