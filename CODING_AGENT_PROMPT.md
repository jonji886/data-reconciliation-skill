# Coding Agent Prompt — Excel / CSV 智能对账与差异定位 Skill（MVP）

你是一名资深 AI 应用工程师 / FDE / 数据工程师。请基于本仓库中的 `README.md`、`SPEC.md`、`TEST_PLAN.md`，实现一个可运行、可测试、可演示的 MVP：

> **Excel / CSV 智能对账与差异定位 Skill**
>
> 用户上传两份 Excel / CSV 数据，系统自动完成数据画像、候选主键识别、候选字段映射、关键映射人工确认、确定性对账、差异分类与报告导出。

---

## 0. 最重要的产品原则

这个项目不是“让 LLM 看两个 Excel”。

核心原则：

1. **LLM 负责语义，不负责确定性计算**
   - 可用于字段语义匹配、差异模式解释、风险提示。
   - 不可用于统计行数、Join、金额求和、Missing Record 数量、Duplicate 数量等确定性任务。

2. **确定性计算必须由代码完成**
   - 使用 Python + Pandas / DuckDB。
   - 相同输入 + 相同规则必须得到相同结果。

3. **不确定时拒绝猜测**
   - 主键、枚举映射、金额单位、日期语义等低置信度情况必须进入 `NEEDS_CONFIRMATION`。
   - 严禁根据“常见情况”偷偷补全业务映射。

4. **所有结论必须可追溯**
   - 对账结果必须能回到原始记录。
   - 生成的报告必须包含差异记录与原因分类。

5. **MVP 只解决一个 Job-to-be-Done**
   - “我有两份 Excel / CSV 数据对不上，请告诉我哪里不一样，并帮助我定位原因。”

---

## 1. MVP 范围

必须完成：

- CSV / XLSX 文件读取
- 多 Sheet 处理：MVP 可要求用户选择 Sheet；如果只有一个 Sheet 自动选择
- 数据 Profile
- 候选主键识别
- 候选字段 Mapping
- Mapping Confidence
- 关键 Mapping 人工确认
- 确定性 Join / Diff
- Missing in A / Missing in B
- Duplicate Key
- Value Mismatch
- 简单数值容差
- 简单日期标准化
- 简单字符串标准化
- 差异原因分类
- Summary
- 导出 Excel 报告
- Mapping Spec 导出
- 可重复运行
- 基础日志
- 自动化测试
- Benchmark：Baseline vs Skill

暂时不要做：

- ERP / CRM / 数据库直连
- API 同步
- MCP
- 云服务
- 多租户
- 登录权限
- Billing
- Dashboard
- 长期任务
- 自动修改源文件
- 自动写回企业系统
- Ontology
- 复杂 Agent Loop
- 100 万行以上性能优化
- 自动枚举值写入而不确认

---

## 2. 推荐技术栈

优先：

- Python 3.11+
- Pandas
- DuckDB（可选但推荐用于对账）
- openpyxl
- Pydantic
- pytest
- Typer 或 argparse
- Streamlit（如果要提供最小可视化 Demo）
- LLM SDK：抽象接口，不绑定单一厂商

LLM 必须通过一个统一接口，例如：

```python
class SemanticMatcher:
    def propose_column_mapping(
        self,
        source_profile: TableProfile,
        target_profile: TableProfile
    ) -> list[MappingSuggestion]:
        ...
```

必须允许：

```python
SemanticMatcher = HeuristicMatcher
```

也就是说，即使没有配置 LLM Key，系统仍应能用启发式规则跑通基础 Demo。

---

## 3. 建议目录结构

```text
.
├── README.md
├── SPEC.md
├── TEST_PLAN.md
├── pyproject.toml
├── src/
│   └── reconcile_skill/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── loaders.py
│       ├── profiler.py
│       ├── key_detector.py
│       ├── semantic_matcher.py
│       ├── mapping.py
│       ├── normalizers.py
│       ├── reconciler.py
│       ├── diagnosis.py
│       ├── report.py
│       ├── config.py
│       └── logging_utils.py
├── tests/
│   ├── test_profiler.py
│   ├── test_key_detector.py
│   ├── test_mapping.py
│   ├── test_reconciler.py
│   ├── test_normalizers.py
│   └── fixtures/
├── examples/
│   ├── case_01_orders/
│   ├── case_02_customers/
│   └── case_03_inventory/
└── outputs/
```

如果你认为有更简单且合理的结构，可以调整，但不要破坏模块边界。

---

## 4. 核心数据模型

至少实现：

```python
class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_ratio: float
    unique_ratio: float
    sample_values: list[str]
    inferred_semantic_type: str | None = None

class TableProfile(BaseModel):
    file_name: str
    sheet_name: str | None
    row_count: int
    columns: list[ColumnProfile]
    candidate_keys: list["KeyCandidate"]

class KeyCandidate(BaseModel):
    columns: list[str]
    score: float
    reasons: list[str]

class MappingSuggestion(BaseModel):
    source_column: str
    target_column: str | None
    confidence: float
    mapping_type: str
    reasons: list[str]
    requires_confirmation: bool

class CompareRule(BaseModel):
    source_column: str
    target_column: str
    rule_type: str
    tolerance: float | None = None
    normalizers: list[str] = []

class ReconciliationSummary(BaseModel):
    source_rows: int
    target_rows: int
    matched_rows: int
    missing_in_source: int
    missing_in_target: int
    duplicate_source_keys: int
    duplicate_target_keys: int
    value_mismatches: int
```

---

## 5. 数据画像 Profile

每个字段至少输出：

- dtype
- null ratio
- unique ratio
- top values
- sample values
- min/max（数值 / 日期适用）
- 最大字符串长度（字符串适用）
- 是否疑似 ID / code / amount / datetime / status / name

不要把完整数据发送给 LLM。

如需调用 LLM，只传：

- column name
- dtype
- sample values（最多 10 个，且需要脱敏）
- basic statistics

---

## 6. 候选主键识别

候选主键评分至少考虑：

- 非空率
- 唯一率
- 值稳定性
- 字段名称特征：
  - id
  - code
  - no
  - number
  - order_id
  - user_id
  - customer_id
- 两张表候选字段的值交集比例

输出示例：

```json
{
  "source": "订单号",
  "target": "order_no",
  "confidence": 0.99,
  "reasons": [
    "两列唯一率均 > 99.9%",
    "值交集率 98.6%",
    "字段名称语义接近"
  ]
}
```

规则：

- confidence >= 0.95：可自动推荐，但执行前仍显示给用户
- 0.75 <= confidence < 0.95：必须确认
- confidence < 0.75：禁止自动选择

---

## 7. 字段 Mapping

使用多信号融合，而不是只靠 LLM：

1. 字段名 exact / normalized match
2. token overlap
3. 常见同义词
4. 数据类型兼容
5. 值分布相似
6. Sample value overlap
7. LLM semantic score（可选）

最终分数必须可解释。

示例：

```text
amount → total_amount
confidence: 0.98
reason:
- semantic name match
- both numeric
- value distribution highly similar
```

低置信度示例：

```text
status → order_state
confidence: 0.71
requires_confirmation: true
reason:
- field names similar
- enum values differ
```

---

## 8. Normalizer

MVP 支持以下标准化：

### String
- trim
- lowercase
- uppercase
- collapse_whitespace

### Number
- numeric parse
- decimal rounding
- tolerance compare

### Datetime
- parse common datetime formats
- normalize timezone only when explicitly configured
- default禁止猜测 timezone

### Null
标准化：
- empty string
- null
- NaN
- "NULL"
- "N/A"

必须可配置。

---

## 9. Reconciliation Engine

执行流程：

```text
Load
→ Profile
→ Select/Confirm Key
→ Propose Mapping
→ Confirm Ambiguous Mapping
→ Normalize
→ Validate Key
→ Join
→ Compare
→ Classify Differences
→ Export Report
```

至少输出以下记录集：

### `missing_in_source`
Target 有、Source 无。

### `missing_in_target`
Source 有、Target 无。

### `duplicate_keys_source`

### `duplicate_keys_target`

### `value_mismatch`

字段至少包括：

- reconciliation_key
- source_column
- target_column
- source_value
- target_value
- normalized_source_value
- normalized_target_value
- difference_type

---

## 10. Difference Classification

MVP 支持：

```text
MISSING_RECORD
DUPLICATE_KEY
VALUE_MISMATCH
NUMERIC_TOLERANCE_MISMATCH
DATETIME_MISMATCH
FORMAT_ONLY_DIFFERENCE
ENUM_MAPPING_REQUIRED
NULL_MISMATCH
UNMAPPED_COLUMN
```

可以增加，但不要过度复杂。

---

## 11. 差异诊断

诊断层可以用规则 + LLM。

例如发现：

- 18/21 条缺失记录 `status=CANCELLED`

可以输出：

```text
Pattern:
18 of 21 missing records have status=CANCELLED.

Hypothesis:
Target dataset may exclude cancelled records.

Confidence:
HIGH

Evidence:
18/21 = 85.7%

Important:
This is a hypothesis, not a confirmed root cause.
```

要求：

- 明确区分 `FACT` 和 `HYPOTHESIS`
- 禁止把统计相关性写成确定原因
- 所有比例由程序计算

---

## 12. 报告输出

必须生成：

```text
reconciliation_report.xlsx
```

至少包含 Sheet：

1. `Summary`
2. `Mapping`
3. `Missing_In_Source`
4. `Missing_In_Target`
5. `Duplicate_Source`
6. `Duplicate_Target`
7. `Value_Mismatch`
8. `Diagnostics`

同时生成：

```text
mapping.yaml
```

示例：

```yaml
version: 1
key:
  source: 订单号
  target: order_no

fields:
  - source: 金额
    target: total_amount
    rule: numeric
    tolerance: 0.01

  - source: 状态
    target: status
    rule: enum
    requires_confirmation: true
```

---

## 13. CLI

至少支持：

```bash
reconcile \
  --source examples/source.xlsx \
  --target examples/target.csv \
  --output outputs/run_001
```

如果存在低置信度项：

```text
Candidate key:
订单号 ↔ order_no
confidence: 0.99
Use this mapping? [Y/n]

Ambiguous mapping:
订单状态 ↔ status
confidence: 0.74
Confirm? [y/N]
```

如果实现 Streamlit，可作为额外入口，但 CLI 必须先完成。

---

## 14. 安全与隐私

MVP 至少满足：

- 默认本地处理文件
- 禁止把完整原始文件发送给 LLM
- LLM 调用仅发送最少字段元数据与脱敏样本
- 日志不得输出完整敏感数据
- README 明确提示：
  - 不建议上传密码、Token、身份证、银行卡等敏感字段
  - 若调用外部模型，用户应理解数据边界

---

## 15. 必须准备的 Example Cases

至少实现 5 个可重复测试样例：

### Case 01：字段名不同但语义一致
`order_id ↔ order_no`

### Case 02：缺失记录
Source 100 行，Target 97 行。

### Case 03：重复主键
Source 存在 3 个重复订单号。

### Case 04：金额容差
100.00 vs 100.001 应在 tolerance=0.01 下视为一致。

### Case 05：枚举值不同
`paid/cancelled` vs `SUCCESS/CLOSED`
必须要求确认映射。

建议额外：

### Case 06：格式差异
`138 0000 0000` vs `13800000000`

### Case 07：日期格式差异
`2026/10/01` vs `2026-10-01`

### Case 08：错误主键诱导
`name` 不唯一，`customer_id` 才是正确主键。

---

## 16. Benchmark

实现 `benchmark/` 或脚本，用来比较：

### Baseline
简单规则 / 或裸 LLM Prompt：
“比较两个文件并找出不同。”

### Skill
完整工作流。

至少记录：

- key identification accuracy
- field mapping precision
- field mapping recall
- missing record recall
- false positive count
- mismatch precision
- human confirmations required
- runtime
- LLM calls
- estimated token usage

Benchmark 不要求做到学术论文级，但必须可重复。

---

## 17. Definition of Done

只有同时满足以下条件才算 MVP 完成：

- [ ] CSV 可运行
- [ ] XLSX 可运行
- [ ] 可识别至少一个候选主键
- [ ] 可提出字段 Mapping
- [ ] 低置信度 Mapping 不会静默自动执行
- [ ] 可检测 Missing Records
- [ ] 可检测 Duplicate Keys
- [ ] 可检测 Value Mismatch
- [ ] 数值 tolerance 生效
- [ ] 可生成 `mapping.yaml`
- [ ] 可生成包含多个 Sheet 的 `reconciliation_report.xlsx`
- [ ] 测试全部通过
- [ ] 至少 5 个 example cases 可运行
- [ ] Benchmark 可运行
- [ ] README 包含 Quick Start
- [ ] 不依赖 LLM 也能跑基础模式
- [ ] 配置 LLM 后可以增加语义 Mapping 能力
- [ ] 所有“可能原因”均标记为 Hypothesis，而不是 Fact

---

## 18. 实现顺序

严格按以下顺序，不要一开始做 UI：

### P0
1. models
2. loaders
3. profiler
4. key detector
5. heuristic mapping
6. reconciliation engine
7. Excel report
8. tests

### P1
9. semantic matcher / LLM adapter
10. confidence gate
11. diagnostics
12. mapping.yaml reuse

### P2
13. Streamlit Demo
14. benchmark polish

---

## 19. 工作方式

请采用：

> SPEC → tests → implementation → examples → benchmark → docs

每完成一个模块：

1. 运行测试。
2. 检查异常输入。
3. 不要用 placeholder 假装完成。
4. 不要创建没有调用链的“空架构”。
5. 先实现最小闭环，再抽象。

如果 SPEC 与实现冲突：
- 优先保证正确性、可复现性和 MVP 简洁性。
- 在 `DECISIONS.md` 中记录重要取舍。

---

## 20. 最终交付物

完成后仓库至少应包含：

```text
README.md
SPEC.md
TEST_PLAN.md
DECISIONS.md
pyproject.toml
src/
tests/
examples/
benchmark/
```

并提供：

```bash
pytest
```

以及：

```bash
reconcile --source ... --target ...
```

两个命令都可以真实运行。

不要只输出代码片段。请直接在仓库中创建、修改、运行、测试并修复，直到 MVP 达到 Definition of Done。
