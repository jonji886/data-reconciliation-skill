# SPEC — Excel / CSV 智能对账与差异定位 Skill（MVP）

## 1. Product Statement

### Problem

业务人员经常遇到：

> 两个系统导出的数据对不上，但不知道应该如何快速、可靠地找到差异。

现有方案通常为：

- VLOOKUP / XLOOKUP；
- Power Query；
- SQL；
- Python；
- 手工筛选；
- 把文件临时交给 LLM 分析。

这些方案的问题不是“做不到”，而是：

- 对非数据专业用户门槛高；
- 每次需要重新配置；
- 容易选择错误主键；
- 对业务枚举和格式差异处理不一致；
- 缺少标准化差异输出；
- 不适合沉淀为可重复交付 SOP。

### Product Promise

用户提供两份 Excel / CSV 后，MVP 帮助完成：

> **识别 → 确认 → 对账 → 定位 → 导出**

---

# 2. User Stories

## US-01 上传数据

作为用户，我希望提供两份 XLSX / CSV 文件，以便进行对账。

Acceptance:

- 支持 `.csv`
- 支持 `.xlsx`
- 文件无法解析时提供明确错误
- 不静默跳过解析失败字段

---

## US-02 数据画像

作为用户，我希望看到系统识别出的行数、字段、数据类型、空值和唯一性，以便理解数据质量。

Acceptance:

至少返回：

- row_count
- column_count
- dtype
- null_ratio
- unique_ratio
- sample_values

---

## US-03 主键推荐

作为用户，我希望系统推荐两份表中可能对应的主键，以避免手工判断。

Acceptance:

- 至少给出 Top 3 candidate
- 包含 confidence
- 包含 reasons
- 低置信度不得自动选择

---

## US-04 字段 Mapping

作为用户，我希望系统自动推荐字段对应关系。

Acceptance:

每个 Mapping：

- source column
- target column
- confidence
- mapping type
- reasons
- requires_confirmation

---

## US-05 高风险确认

作为用户，我希望系统在不确定时先询问我，而不是擅自执行。

强制确认：

- 主键低置信度
- enum mapping
- timezone
- amount unit
- 多字段复合映射
- 一对多映射

---

## US-06 对账

作为用户，我希望系统找出：

- Source 独有
- Target 独有
- Source 重复
- Target 重复
- 字段值不一致

Acceptance:

所有计算必须由 deterministic code 完成。

Value comparison has three outcomes: `MATCH`, confirmed `MISMATCH`, and
`UNVERIFIED`. A parse failure, non-finite number, ambiguous date, or mixed
timezone awareness is never converted into a string match.

---

## US-07 容差

作为用户，我希望金额等数值支持 tolerance。

例如：

```text
100.00
100.001
```

当 tolerance = 0.01：

应视为一致。

---

## US-08 格式标准化

MVP 支持：

- whitespace normalization
- case normalization
- numeric parsing
- datetime parsing
- null normalization

禁止：

- 未经确认自动转换时区
- 未经确认自动推断金额单位

---

## US-09 差异报告

作为用户，我希望下载一个 Excel 报告。

必须包含：

- Summary
- Mapping
- Missing_In_Source
- Missing_In_Target
- Duplicate_Source
- Duplicate_Target
- Value_Mismatch
- Diagnostics

When applicable, the report also contains `Unverified` and `Field_Coverage`.
Summary must show their counts and a status other than complete success when
any value or field was not actually verified.

---

## US-10 保存 Mapping

作为用户，我希望把 Mapping 保存为 YAML，以便重复执行。

---

# 3. Functional Requirements

## FR-01 Loader

CSV：

- UTF-8
- UTF-8-SIG
- 常见分隔符

XLSX：

- sheet listing
- single sheet auto-select
- multiple sheets requires selection

---

## FR-02 Profiler

Field statistics：

```text
dtype
null_count
null_ratio
unique_count
unique_ratio
top_values
sample_values
min
max
max_length
```

---

## FR-03 Key Detector

Scoring factors：

```text
uniqueness
null rate
column name
cross-table value overlap
datatype compatibility
```

---

## FR-04 Mapping Engine

Signals：

```text
exact name
normalized name
token similarity
synonym
datatype compatibility
sample overlap
distribution similarity
LLM semantic score(optional)
```

---

## FR-05 Confidence Gate

Suggested thresholds:

```text
>= 0.95
HIGH
推荐自动接受，但展示给用户

0.75 - 0.95
MEDIUM
需要确认

< 0.75
LOW
不得自动执行
```

Enum Mapping 默认至少 MEDIUM 风险。

---

## FR-06 Reconciliation

默认 Join：

```text
FULL OUTER JOIN
```

通过 reconciliation key 区分：

```text
source only
target only
both
```

对于 `both`：

逐 Mapping 字段比较。

An empty rule list is a partial reconciliation, even when every key matches.
Unmapped, pending-confirmation, skipped and unsupported fields are tracked as
coverage gaps and are not counted as compared fields.

---

## FR-07 Diagnostics

至少实现简单聚类：

Missing diagnostics are generated independently for `Missing_In_Source`
(Target-only records) and `Missing_In_Target` (Source-only records). Each
diagnostic carries its direction, evidence count and a hypothesis explicitly
marked as non-causal.

例如：

```text
missing_in_target records
group by:
status
type
region
category
```

检测是否存在：

```text
top category ratio >= configured threshold
```

如：

```text
18/21 status=CANCELLED
```

则输出：

```text
Fact:
18 of 21 missing records have status=CANCELLED.

Hypothesis:
A filtering rule related to CANCELLED status may exist.
```

---

# 4. Non-functional Requirements

## NFR-01 Determinism

确定性计算不可依赖 LLM。

## NFR-02 Reproducibility

保存：

- mapping
- config
- input file hashes
- software version
- run timestamp

## NFR-03 Privacy

默认本地运行。

## NFR-04 Observability

至少记录：

```text
run_id
source file
target file
row counts
selected key
mapping count
warnings
runtime
LLM calls
```

日志禁止输出完整业务数据。

## NFR-05 Error Handling

错误必须明确区分：

```text
FILE_ERROR
SCHEMA_ERROR
KEY_NOT_FOUND
AMBIGUOUS_MAPPING
DUPLICATE_KEY
UNSUPPORTED_TYPE
LLM_ERROR
REPORT_ERROR
```

---

# 5. State Model

建议 Run 状态：

```text
CREATED
LOADED
PROFILED
WAITING_KEY_CONFIRMATION
WAITING_MAPPING_CONFIRMATION
READY
RUNNING
COMPLETED
FAILED
```

---

# 6. Output Schema

## Summary

```json
{
  "source_row_count": 10028,
  "target_row_count": 9987,
  "matched_key_count": 9970,
  "matched_unique_key_count": 9970,
  "missing_source_key_count": 5,
  "missing_source_row_count": 5,
  "missing_target_key_count": 41,
  "missing_target_row_count": 41,
  "duplicate_source_key_count": 3,
  "duplicate_source_row_count": 6,
  "duplicate_target_key_count": 1,
  "duplicate_target_row_count": 2,
  "value_mismatch_count": 17,
  "unverified_count": 0,
  "compared_field_count": 4,
  "pending_field_count": 0,
  "coverage_status": "COMPLETE",
  "reconciliation_status": "COMPLETED_WITH_DIFFERENCES"
}
```

`unverified_count` is a cell-level count. `unverified_field_count` and the
field coverage counts are field-level values and must not be added to the cell
count. `PARTIAL_NEEDS_REVIEW` is the required status whenever comparison
coverage is incomplete or an unverified value exists.

The legacy summary names remain available in the Python/API log output for
backward compatibility. The Excel Summary sheet uses the explicit key/row
names above.

---

# 7. Security Boundaries

禁止：

- 自动上传完整 Excel 到第三方 LLM；
- 日志打印 Access Token；
- 日志打印完整身份证/银行卡；
- 未经用户确认修改原始数据；
- 把推测原因写成确定根因。

---

# 8. MVP Limitations

明确接受：

- 不处理复杂多表关系；
- 不解决极大规模数据；
- 不做自动修复；
- 不做完整数据治理；
- 不保证语义 Mapping 100% 准确；
- 不尝试理解企业内部所有业务规则。

---

# 9. Product Metrics

发布后建议采集：

```text
skill_download
first_run
reconciliation_completed
mapping_confirmation
report_exported
repeat_run
error
```

核心指标：

```text
First Run Completion Rate
Report Export Rate
Repeat Usage Rate
Mapping Acceptance Rate
Badcase Rate
```

---

# 10. MVP Release Gate

上线前：

- 5+ fixture cases 全部通过
- 所有确定性测试通过
- Enum case 不会自动猜测
- Wrong key case 能阻止错误自动选择
- 报告可打开
- Mapping YAML 可重复使用
- 无 LLM Key 情况基础功能正常
