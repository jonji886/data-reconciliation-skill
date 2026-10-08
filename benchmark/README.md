# Benchmark

`run_benchmark.py` runs the complete local workflow for 25 synthetic cases and
10 anonymized realistic CSV fixtures in `benchmark/real_world/`.

```text
Load → Profile → Detect Key → Mapping → Confirmation simulation → Reconcile → Evaluate
```

The golden key, mapping, missing-record and mismatch labels are used only after
prediction to evaluate accuracy. They are never passed to `reconcile()` to
select a key or generate a result. The benchmark confirmation policy explicitly
confirms non-enum, non-collision proposals; enum mappings remain pending. A
confirmed high-risk proposal is not counted as silent execution.

The dataset covers English, Chinese and mixed-language fields; wrong-key and
composite-looking traps; missing and duplicate records; null keys; numeric
tolerance; amount/date/string formatting; case sensitivity; enum, SKU,
customer, inventory, payment, order and migration scenarios.

Baseline A is exact normalized column-name matching. Baseline B is a name-only semantic heuristic. Neither baseline runs deterministic reconciliation with the golden key.

Run:

```bash
uv run python benchmark/run_benchmark.py
```

The command writes [`results.json`](results.json), including:

- Key Detection Accuracy
- Mapping Precision / Recall / F1
- Missing Record Precision / Recall / F1
- Mismatch Precision / Recall / F1
- False Positive Count and Silent High-risk Mapping
- Runtime and LLM Calls
- Per-case results and both baselines

The run also writes `CORRECTNESS_AUDIT.md`. It audits every golden Value
Mismatch that was not detected and records the Case ID, actual result, selected
key, mapping selection, whether the case entered comparison, safe-policy skip,
parse failure, algorithm-error classification and Golden Label assessment.
`confirmed_false_negative_count` counts only cases that entered deterministic
comparison and still failed to report the expected mismatch. Enum cases that
remain pending human confirmation are retained in end-to-end coverage and are
reported separately as safe-policy skips.

`results.json` is the source of truth for current numbers. Missing records are
evaluated as sets of reconciliation keys per direction. Value mismatches are
evaluated as sets of `(reconciliation_key, source_column, target_column,
difference_type)`. The benchmark is a small deterministic heuristic
evaluation, not evidence of production-scale accuracy; real files may contain
domain-specific semantics, ambiguous dates, units or one-to-many relationships
that still require user confirmation.
