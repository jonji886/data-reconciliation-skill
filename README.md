# Excel / CSV 智能对账与差异定位 Skill

> 两份数据对不上时，自动帮助用户识别“哪里不同、差多少、可能为什么不同”。

## 1. 为什么做这个项目

企业里的数据问题通常不是“不会分析 Excel”，而是：

- ERP 导出了 10,028 条，目标系统只有 9,987 条；
- CRM 客户表和销售维护的 Excel 对不上；
- 平台订单和 ERP 订单数量不一致；
- 两个系统字段名称不同、状态编码不同；
- 数据迁移后需要验证是否少数据、重复数据或值发生变化；
- 实施、运营、财务或技术支持人员知道“数据有问题”，但不一定知道应该如何 Join、如何选择主键、如何写脚本。

直接把两份 Excel 丢给通用 LLM 可以完成一次性分析，但容易出现：

- 每次都要重新解释规则；
- 主键选择错误；
- LLM 对确定性数字进行推断；
- 枚举值被“猜测映射”；
- 结果难以复现；
- 没有结构化差异报告；
- 下次无法重复执行同一套 Mapping。

本项目的目标不是替代 Excel，也不是做一个“Excel 聊天助手”。

目标是把一次性的人工核对流程固化成：

> **Profile → Mapping → Confirmation → Deterministic Reconciliation → Diagnosis → Evidence Report**

---

## 2. 核心价值

### 对普通用户

用户只需要回答：

> “这两个表为什么对不上？”

系统负责：

1. 读取两份数据；
2. 分析字段；
3. 推荐主键；
4. 推荐字段对应关系；
5. 要求用户确认高风险 Mapping；
6. 自动对账；
7. 找出缺失、重复、字段不一致；
8. 输出 Excel 差异报告。

### 对企业交付

本项目重点体现：

- LLM 与确定性代码的边界；
- Human-in-the-loop；
- Confidence Gate；
- 可验证结果；
- Mapping Spec；
- Reconciliation；
- Evidence；
- Regression / Benchmark；
- 数据隐私边界。

因此它更接近一个小型企业 Data Integration QA 工具，而不是 Prompt Demo。

---

## 3. 谁会使用

主要目标用户：

- SaaS 实施顾问
- FDE / Solution Engineer
- ERP / CRM 实施
- 数据运营
- 电商运营
- 财务运营
- 技术支持
- 客户成功
- 需要做系统迁移或数据核对的业务人员

---

## 4. MVP Job-to-be-Done

MVP 只解决：

> **我有两份 Excel / CSV，它们对不上。请告诉我哪里不一样，并尽可能帮助我定位差异原因。**

MVP 不解决：

- 企业系统直连；
- 自动修复线上数据；
- 自动执行高风险变更；
- 大规模 ETL；
- BI Dashboard；
- 完整 MDM / 数据治理。

---

## 5. MVP 工作流

```text
Source.xlsx / csv
        +
Target.xlsx / csv
        ↓
Data Profile
        ↓
Candidate Key Detection
        ↓
Column Mapping Proposal
        ↓
Confidence Gate
        ↓
Human Confirmation
        ↓
Normalization
        ↓
Deterministic Reconciliation
        ↓
Difference Classification
        ↓
Pattern Diagnosis
        ↓
Evidence Report
```

---

## 6. 为什么不直接使用 ChatGPT

这个项目不假设模型比 ChatGPT 更聪明。

优势来自 Workflow：

| 通用 LLM | 本 Skill |
|---|---|
| 一次性聊天 | 可重复流程 |
| 用户自己组织 Prompt | 固定 SOP |
| 容易混合语义与计算 | 语义归 LLM，计算归代码 |
| 可能猜业务规则 | 低置信度强制确认 |
| 自由文本 | Structured Output |
| 每次重新定义 Mapping | Mapping Spec 可复用 |
| 看起来有道理 | 可验证差异记录 |
| 难做 Regression | 可以 Benchmark / Regression |

---

## 7. MVP 输出

运行结束必须生成：

### `reconciliation_report.xlsx`

包含：

- Summary
- Mapping
- Missing_In_Source
- Missing_In_Target
- Duplicate_Source
- Duplicate_Target
- Value_Mismatch
- Diagnostics

### `mapping.yaml`

用于复用本次确认后的 Mapping 规则。

---

## 8. 核心原则

### 8.1 确定性优先

这些任务必须由 Python / SQL / DuckDB 完成：

- Row count
- Join
- Duplicate
- Missing records
- Sum
- Numeric diff
- Value comparison

### 8.2 LLM 只做语义

适合：

- 字段语义相似度；
- 数据含义判断；
- 差异模式解释；
- 人类可读说明。

### 8.3 不确定就确认

特别是：

- 主键
- 枚举值
- 金额单位
- 时区
- 一对多关系

不得静默猜测。

### 8.4 Fact 和 Hypothesis 分离

例如：

**FACT**

> 21 条记录只存在 Source。

**FACT**

> 其中 18 条 status=CANCELLED。

**HYPOTHESIS**

> Target 系统可能过滤 CANCELLED 数据。

禁止把 Hypothesis 写成 Root Cause。

---

## 9. 设计目标

### Reliability

相同输入与规则产生相同结果。

### Explainability

每个 Mapping 推荐都能解释原因。

### Traceability

每条异常能够回到原始数据。

### Safety

低置信度规则需要确认。

### Reusability

确认后的 Mapping 可以保存并复用。

### Testability

所有核心逻辑都有自动化测试。

---

## 10. MVP 成功标准

MVP 技术完成 ≠ 产品验证成功。

### 技术成功

- 两文件可运行；
- 自动识别候选主键；
- 自动提出 Mapping；
- 能识别缺失、重复、字段差异；
- 可输出 Excel 报告；
- 关键误判会进入人工确认。

### 产品验证

发布后建议跟踪：

- 下载量；
- 首次运行成功率；
- 完成一次真实对账的用户数；
- Mapping 人工确认率；
- 用户再次使用率；
- Badcase 类型。

建议 Gate：

1. **50+ 下载**：说明标题/场景具备初步吸引力；
2. **10 个真实任务**：说明不是纯 Demo；
3. **至少 3 个重复使用者或明确复用意图**：说明存在留存；
4. 如果大多数人只需要“简单找不同”，停止扩展复杂 Agent。

---

## 11. Skill 商店定位

建议展示名：

> **Excel / CSV 智能对账助手**

副标题：

> 两个表自动匹配字段，找出缺失、重复、金额、状态和字段差异。

可覆盖搜索词：

- Excel 对账
- CSV 对账
- 两表比较
- 表格核对
- 数据核对
- 找不同
- 数据匹配
- VLOOKUP
- 订单对账
- 数据差异
- ERP 对账
- CRM 数据核对
- 数据迁移校验

不要把市场名称写成：

> Enterprise Schema Mapping Agent

这适合作品集介绍，不适合普通用户搜索。

---

## 12. 作品集说明

面试时，这个项目重点不是：

> “我做了一个 Excel Skill。”

而是：

> “我把企业数据交付中的 Mapping、校验、对账、人工确认、异常定位和证据链，做成了一个可重复执行的 AI Workflow。”

可以重点解释：

- 为什么统计不能交给 LLM；
- 为什么 Mapping 需要 Confidence；
- 为什么枚举必须人工确认；
- 为什么需要 Mapping Spec；
- 如何设计 Benchmark；
- 如何避免把相关性误判成根因；
- 如何控制隐私；
- 如何处理 Schema Drift。

---

## 13. Architecture

```text
Host Agent / LLM
        │
        ├── Intent
        ├── Semantic Mapping
        ├── Clarification
        └── Explanation
        │
        ▼
Deterministic Engine
        │
        ├── Profile
        ├── Key Detection
        ├── Mapping
        ├── Join
        ├── Diff
        ├── Evidence
        └── Excel Report
```

> LLM handles ambiguity. Code handles truth.

重复键会单独进入 Duplicate sheet，并排除在普通 record-level value comparison 之外；确认后的 Mapping 可通过 YAML 重复运行。

### Reliability principles

- Deterministic computation: row counts, joins, missing/duplicate records, tolerance and mismatch identities come from Python.
- Human confirmation: ambiguous keys, low-confidence mappings, collisions and enum differences do not execute silently.
- Case-sensitive identifiers by default: `ABC001` and `abc001` are different unless the saved key rule explicitly opts out.
- Duplicate isolation: duplicate keys remain visible in their dedicated report sheets and are excluded from ordinary value comparison.
- Evidence-based reporting: every mismatch carries its reconciliation key, source/target columns, values and difference type.

## 14. Security

- Local-first：文件默认只在本地读取和处理，当前默认 matcher 不需要 LLM Key。
- Minimal LLM data exposure：日志仅记录文件名、SHA-256、规则元数据和摘要，不记录完整数据行。
- Excel report 对用户来源的 `=`, `+`, `-`（非纯数值）和 `@` 前缀做文本转义，防止 Formula Injection。
- 不静默推断业务枚举、金额单位、时区、一对多关系或冲突 Mapping。
- 不自动修改用户原始 Excel；事实与假设分离，不把 Hypothesis 写成 Root Cause。

## 15. Benchmark

Benchmark 包含 25 个 synthetic case 和 10 个 anonymized realistic fixture，覆盖中英文 Mapping、错误主键陷阱、缺失/重复/null、数值容差、日期、大小写、枚举、SKU、客户、库存、支付、订单和迁移场景。

运行：

```bash
uv run python benchmark/run_benchmark.py
```

当前结果由 [`benchmark/results.json`](benchmark/results.json) 真实生成；该文件是指标唯一事实来源。Missing 和 mismatch 使用具体 identity 的 set-based Precision/Recall/F1，而不是只比较数量；同时记录 Key Detection Accuracy、Mapping Precision/Recall/F1、False Positive、Silent High-risk Mapping、Runtime 和 LLM Calls。详细设计和局限见 [`benchmark/README.md`](benchmark/README.md)。

枚举值目前只检测差异并要求人工确认，不会自动把 `paid` 猜成 `SUCCESS`。

## 16. Quick Start

需要 Python 3.11+。项目默认本地运行，不需要 LLM Key：

```bash
uv sync --extra dev
uv run reconcile \
  --source examples/case_01_orders/source.csv \
  --target examples/case_01_orders/target.csv \
  --output outputs/case_01
```

命令会在低置信度主键、枚举字段或其他高风险 Mapping 处要求确认；拒绝确认时不会继续执行。后续可复用已确认的规则：

```bash
uv run reconcile \
  --source examples/case_01_orders/source.csv \
  --target examples/case_01_orders/target.csv \
  --mapping outputs/case_01/mapping.yaml \
  --output outputs/case_01_repeat
```

测试与 benchmark：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run pytest -q
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run python benchmark/run_benchmark.py
```

Summary 报告明确区分 `Matched Unique Keys`、`Missing ... Keys/Rows` 和 `Duplicate ... Keys/Rows`；旧版 API 字段仍保留为兼容别名。

## 17. Limitation

MVP currently does not infer arbitrary enterprise business rules automatically.
金额单位、时区、一对多关系以及枚举 value mapping 仍需要人工确认或显式配置。

## 18. 下一阶段可能扩展

只有 MVP 得到真实使用验证后，再考虑：

- 保存 Project；
- Mapping Template；
- Regression；
- 多次 Run 对比；
- Schema Drift；
- 数据库连接；
- API；
- ERP / CRM Connector；
- Scheduled Reconciliation；
- Webhook；
- MCP；
- 大文件优化。

不要在 MVP 阶段提前实现。
