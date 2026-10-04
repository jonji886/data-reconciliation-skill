"""Privacy-conscious run metadata logging."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from . import __version__
from .models import ReconciliationResult


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_run_log(
    output_dir: str | Path,
    *,
    source_path: str | Path,
    target_path: str | Path,
    source_key: str,
    target_key: str,
    result: ReconciliationResult,
    started_at: float,
    key_case_sensitive: bool = True,
) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": result.run_id,
        "run_timestamp": result.run_timestamp.isoformat(),
        "software_version": __version__,
        "source_file": Path(source_path).name,
        "target_file": Path(target_path).name,
        "source_sha256": sha256_file(source_path),
        "target_sha256": sha256_file(target_path),
        "source_key": source_key,
        "target_key": target_key,
        "key_case_sensitive": key_case_sensitive,
        "mapping_count": len(result.mapping),
        "warnings": result.warnings,
        "llm_calls": 0,
        "runtime_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "summary": result.summary.model_dump(),
    }
    path = output / "run_log.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
