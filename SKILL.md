---
name: data-reconciliation
description: Compare two Excel or CSV datasets and identify missing, duplicate, and mismatched records using deterministic reconciliation.
slug: jonji886-data-reconciliation
displayName: Excel / CSV 智能对账助手
version: 0.1.0
summary: 自动比较两份 Excel / CSV 数据，识别字段映射并定位缺失、重复和值差异，输出可追溯的对账报告。
license: MIT
---

# Excel / CSV 数据对账 Skill

## 何时触发

当用户要求核对或比较两份 Excel/CSV、查找缺失订单或客户、验证数据迁移、解释 ERP/CRM/系统导出数量不一致，或询问“两张表为什么对不上”时使用。

典型表达包括：

- 帮我核对这两个 Excel / 比较两个 CSV
- 找出两张表的不同、缺失订单或重复数据
- 检查数据迁移结果、ERP 与系统数据是否一致
- CRM 和 Excel 数据对不上，帮我定位原因

## 标准工作流

1. 接收 Source 与 Target 文件，运行 Profile，展示文件、行数、字段、空值和候选主键。
2. 运行 Candidate Key Detection。主键不确定时必须询问用户；用户可以选择候选、手动指定存在的 Source/Target 字段，或退出。
3. 生成 Column Mapping Proposal。用户可以接受候选、选择其他候选、跳过或手动指定目标字段；字段不存在时拒绝继续该 Mapping。
4. 枚举、金额单位、时区、一对多关系、低置信度 Mapping 和 Mapping collision 必须人工确认，不能静默推断。
5. 将已确认的规则交给 deterministic engine，执行 Join、Duplicate、Missing、Value Diff、Tolerance 和 Evidence 计算。
6. 输出 `reconciliation_report.xlsx`、`mapping.yaml` 和 `run_log.json`，并用 Fact / Hypothesis 分离的方式解释主要异常。报告同时明确显示 `MATCH`、`MISMATCH`、`UNVERIFIED` 和字段覆盖状态。

## Execution

The deterministic reconciliation engine is implemented in Python. Run from the
skill root after the user confirms the key and mappings:

```bash
uv run reconcile \
  --source "<SOURCE_FILE>" \
  --target "<TARGET_FILE>" \
  --output "<OUTPUT_DIR>"
```

To reuse a previously confirmed mapping:

```bash
uv run reconcile \
  --source "<SOURCE_FILE>" \
  --target "<TARGET_FILE>" \
  --mapping "<MAPPING_FILE>" \
  --output "<OUTPUT_DIR>"
```

The command writes the Excel evidence report, reusable `mapping.yaml`, and
privacy-conscious `run_log.json`. Identifiers are case-sensitive by default;
an explicit saved mapping may set `key.case_sensitive: false`.

## 职责边界

Host LLM / Skill 负责意图理解、业务上下文澄清、字段语义判断、模糊 Mapping 辅助、用户确认和结果解释。

Python deterministic engine 负责 Data Profile、Key scoring、Join、Duplicate、Missing、数值比较、容差、证据和 Excel 报告。行数、统计、匹配、差异和聚合不得交给 LLM 猜测。

## Agent behavior

The Agent may:

- explain the user's reconciliation intent;
- show candidate keys and candidate field mappings with confidence and reasons;
- ask the user to confirm or manually select a key or mapping;
- skip unresolved mappings and explain the resulting report;
- explain `FACT` and `HYPOTHESIS` separately.

The Agent must not:

- silently accept a low-confidence key, enum mapping, or mapping collision;
- silently change a saved mapping or lower-case an identifier;
- modify the user's source files;
- upload complete files to a third-party LLM;
- describe a hypothesis as a confirmed root cause.

## 安全与正确性约束

- 默认保守：不确定就询问，不推断枚举、时区、金额单位或一对多规则。
- Duplicate key 只进入 `Duplicate_Source` / `Duplicate_Target`，所有对应原始行都保留；重复键不参与普通 record-level value comparison。
- 普通字符串默认只做 trim 与连续空白归一化，不默认 lowercase；SKU、code、external_id 等默认区分大小写。
- Key normalization is configurable with `trim`, `collapse_whitespace`, and explicit `case_sensitive: false`; `ABC001` and `abc001` are different by default.
- 普通 Mapping 必须一对一；多 Source 映射到同一 Target 时标记 `MAPPING_COLLISION` 并要求用户处理。
- 当前 MVP 只检测枚举值差异；不同枚举值不会自动视为等价，必须由用户确认后再配置业务规则。
- 报告写入 Excel 前必须转义用户来源的公式样式字符串，防止 Spreadsheet Formula Injection。
- 严格数值/日期解析失败、非有限数值和缺少时区的数据进入 `UNVERIFIED`，不得退回字符串比较或计入 MATCH。
- 空的比较规则列表、未映射字段、待人工确认字段和不支持的规则必须显示为部分完成，不得宣称完整对账成功。
- 文件默认本地处理；日志只记录文件名、哈希、规则元数据和摘要，不记录完整敏感数据。

## 输出解释

先报告可验证事实，例如 Source/Target 行数、匹配数、缺失数、重复键数和值差异数；再报告基于分布的假设，并明确说明假设不是已确认根因。

## Interaction example

```text
User: 帮我看看 ERP.xlsx 和 system.xlsx 为什么对不上。

Skill:
Source: 12,382 rows
Target: 12,361 rows

Candidate key:
1. 订单号 ↔ order_id
confidence: 0.98

Identifiers are case-sensitive by default. Use this key?
```

```text
FACT
18 / 21 missing records have status=CANCELLED.

HYPOTHESIS
Target data may exclude CANCELLED records.
```
