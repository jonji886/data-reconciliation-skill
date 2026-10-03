# Benchmark

`run_benchmark.py` runs the complete local workflow for 25 synthetic cases:

```text
Load → Profile → Detect Key → Mapping → Confirmation simulation → Reconcile → Evaluate
```

The golden key and mapping labels are used only after prediction to evaluate accuracy. They are never passed to `reconcile()` to generate a result. The confirmation simulator accepts only non-high-risk mappings; enum and ambiguous mappings remain pending, so `silent_high_risk_mapping` is a hard safety metric.

The dataset covers English, Chinese and mixed-language fields; wrong-key and composite-looking traps; missing and duplicate records; null keys; numeric tolerance; amount/date/string formatting; case sensitivity; enum, SKU, customer, inventory, payment, order and migration scenarios.

Baseline A is exact normalized column-name matching. Baseline B is a name-only semantic heuristic. Neither baseline runs deterministic reconciliation with the golden key.

Run:

```bash
uv run python benchmark/run_benchmark.py
```

The command writes [`results.json`](results.json), including:

- Key Detection Accuracy
- Mapping Precision / Recall
- Missing Record Recall
- Mismatch Precision
- False Positive Count
- Confirmation Safety
- Runtime and LLM Calls
- Per-case results and both baselines

`results.json` is the source of truth for current numbers. The benchmark is a small deterministic heuristic evaluation, not evidence of production-scale accuracy; real files may contain domain-specific semantics, ambiguous dates, units or one-to-many relationships that still require user confirmation.
