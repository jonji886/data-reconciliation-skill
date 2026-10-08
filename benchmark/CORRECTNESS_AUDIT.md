# Correctness Audit

本文件由 `benchmark/run_benchmark.py` 根据当前代码重新生成。Golden labels 未被修改；每条预期 Value Mismatch 都保留其是否真正进入比较流程的审计信息。

## 指标定义

- Cases: 35
- 原始 Value Mismatch Recall: 0.4444
- 已执行比较中的预期差异数: 4
- 安全策略跳过的预期差异数: 5
- 无法可靠比较的预期差异数: 0
- 实际确认的 False Negative（已进入比较且不是 UNVERIFIED）: 0

## False Negative 逐例审计

### 1. enum_status

- Case ID: `enum_status`
- Expected Mismatch: `['A1', 'status', 'status', 'ENUM_MAPPING_REQUIRED']`
- Actual Result: `NOT_COMPARED`
- Selected Key: `['order_id', 'order_id']`
- Key Correct: `True`
- Mapping Generated: `True`
- Mapping Pair Selected: `False`
- Entered Comparison: `False`
- Safe Policy Skipped: `True`
- Parse Failure: `False`
- Real Algorithm Error: `False`
- Golden Label Issue: `False`
- Classification: `CONFIRMATION_PENDING`
- Reason: Enum/high-risk mapping was intentionally not auto-confirmed.

### 2. real_erp_order

- Case ID: `real_erp_order`
- Expected Mismatch: `['O001', '订单状态', 'status', 'ENUM_MAPPING_REQUIRED']`
- Actual Result: `NOT_COMPARED`
- Selected Key: `['订单号', 'order_id']`
- Key Correct: `True`
- Mapping Generated: `True`
- Mapping Pair Selected: `False`
- Entered Comparison: `False`
- Safe Policy Skipped: `True`
- Parse Failure: `False`
- Real Algorithm Error: `False`
- Golden Label Issue: `False`
- Classification: `CONFIRMATION_PENDING`
- Reason: Enum/high-risk mapping was intentionally not auto-confirmed.

### 3. real_erp_order

- Case ID: `real_erp_order`
- Expected Mismatch: `['O002', '订单状态', 'status', 'ENUM_MAPPING_REQUIRED']`
- Actual Result: `NOT_COMPARED`
- Selected Key: `['订单号', 'order_id']`
- Key Correct: `True`
- Mapping Generated: `True`
- Mapping Pair Selected: `False`
- Entered Comparison: `False`
- Safe Policy Skipped: `True`
- Parse Failure: `False`
- Real Algorithm Error: `False`
- Golden Label Issue: `False`
- Classification: `CONFIRMATION_PENDING`
- Reason: Enum/high-risk mapping was intentionally not auto-confirmed.

### 4. real_enum_difference

- Case ID: `real_enum_difference`
- Expected Mismatch: `['O001', 'status', 'status', 'ENUM_MAPPING_REQUIRED']`
- Actual Result: `NOT_COMPARED`
- Selected Key: `['order_id', 'order_id']`
- Key Correct: `True`
- Mapping Generated: `True`
- Mapping Pair Selected: `False`
- Entered Comparison: `False`
- Safe Policy Skipped: `True`
- Parse Failure: `False`
- Real Algorithm Error: `False`
- Golden Label Issue: `False`
- Classification: `CONFIRMATION_PENDING`
- Reason: Enum/high-risk mapping was intentionally not auto-confirmed.

### 5. real_enum_difference

- Case ID: `real_enum_difference`
- Expected Mismatch: `['O002', 'status', 'status', 'ENUM_MAPPING_REQUIRED']`
- Actual Result: `NOT_COMPARED`
- Selected Key: `['order_id', 'order_id']`
- Key Correct: `True`
- Mapping Generated: `True`
- Mapping Pair Selected: `False`
- Entered Comparison: `False`
- Safe Policy Skipped: `True`
- Parse Failure: `False`
- Real Algorithm Error: `False`
- Golden Label Issue: `False`
- Classification: `CONFIRMATION_PENDING`
- Reason: Enum/high-risk mapping was intentionally not auto-confirmed.
