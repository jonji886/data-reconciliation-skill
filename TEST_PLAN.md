# TEST PLAN — Excel / CSV 智能对账与差异定位 Skill

## 1. 测试目标

验证：

1. 结果正确；
2. 错误不会被静默忽略；
3. 低置信度场景不会擅自决策；
4. 报告可追溯；
5. 同样输入可以重复得到同样结果。

---

# 2. Golden Cases

## Case 01 — 字段名不同

Source:

```csv
order_id,amount
A001,100
A002,200
```

Target:

```csv
order_no,total_amount
A001,100
A002,200
```

Expected:

```text
order_id → order_no
amount → total_amount
matched = 2
mismatch = 0
```

---

## Case 02 — Missing Record

Source:

```text
A001
A002
A003
```

Target:

```text
A001
A003
```

Expected:

```text
missing_in_target:
A002
```

---

## Case 03 — Duplicate Key

Source:

```text
A001
A001
A002
```

Expected:

```text
duplicate_source_keys = 1 key
```

系统必须警告：

> 主键不满足唯一性。

---

## Case 04 — Numeric Tolerance

Source:

```text
100.000
```

Target:

```text
100.005
```

Tolerance:

```text
0.01
```

Expected:

```text
MATCH
```

---

## Case 05 — Enum Mapping

Source:

```text
paid
cancelled
```

Target:

```text
SUCCESS
CLOSED
```

Expected:

```text
ENUM_MAPPING_REQUIRED
```

禁止：

```text
paid → SUCCESS
```

在未确认情况下直接执行。

---

## Case 06 — Format Only

Source:

```text
" Alice "
```

Target:

```text
"Alice"
```

Normalizer:

```text
trim
```

Expected:

```text
MATCH
```

---

## Case 07 — Date Format

Source:

```text
2026/10/01
```

Target:

```text
2026-10-01
```

Expected after parsing:

```text
MATCH
```

---

## Case 08 — Wrong Key

Source:

```text
customer_id,name
C001,Alice
C002,Alice
```

Target:

```text
client_id,name
C001,Alice
C002,Alice
```

Expected:

```text
customer_id ↔ client_id
```

系统不得把：

```text
name
```

自动选为主键。

---

# 3. Edge Cases

必须覆盖：

- 空文件
- 只有 Header
- 两个文件字段完全不同
- 两个文件没有可用 Key
- Key 有 Null
- Key 大量重复
- CSV Encoding 错误
- Excel 多 Sheet
- 数值列混入字符串
- 日期解析失败
- 100% Null 列
- 超长字符串
- 相同字段名但不同含义
- 同义字段名但类型不一致

---

# 4. Regression Tests

每个确认过的 Badcase 都加入：

```text
tests/regression/
```

格式建议：

```text
case_id
input_source
input_target
mapping
expected_summary
expected_mismatches
```

原则：

> 修过一次的问题不能在下一版本重新出现。

---

# 5. Benchmark Design

## Baseline A

纯字段名相等：

```text
source column name == target column name
```

## Baseline B

简单 LLM Prompt：

```text
请分析两张表字段对应关系并找出数据差异。
```

## Skill

完整流程。

---

## Metrics

### Key Detection Accuracy

```text
correct_key / all_cases
```

### Mapping Precision

```text
correct_mappings / suggested_mappings
```

### Mapping Recall

```text
correct_mappings / expected_mappings
```

### Missing Record Recall

```text
detected_missing / actual_missing
```

### False Positive

错误标记为异常的记录数量。

### Confirmation Safety

测试集所有需要人工确认项中：

```text
silent_auto_execution = 0
```

必须是硬性要求。

---

# 6. Product Validation Cases

技术测试之外，发布后至少收集 10 个真实任务，建议分类：

1. ERP vs 系统订单
2. 平台订单 vs ERP
3. CRM vs Excel
4. 客户名单 vs CRM
5. 库存 vs WMS
6. 支付记录 vs 订单
7. 商品主数据
8. 数据迁移前后
9. 员工账号
10. API 导出 vs Excel

每个案例记录：

```text
用户角色
任务描述
文件规模
Mapping数量
人工确认数量
异常数量
是否解决问题
用户是否愿意再次使用
Badcase
```

---

# 7. Go / No-Go

## GO

满足任意多数条件：

- > 50 下载
- >= 10 个真实对账任务
- >= 3 个重复使用用户或明确复用意向
- 用户愿意下载报告
- 用户真实需要 Mapping 复用

## NO-GO / Pivot

若出现：

- 用户主要只要简单 VLOOKUP；
- 用户几乎不需要语义 Mapping；
- 复杂功能几乎没人使用；
- 通用 ChatGPT 已完全满足用户需求；

则停止继续做复杂 Agent，转为：

```text
简单两表对账工具
```

或者结束项目。
