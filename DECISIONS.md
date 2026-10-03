# DECISIONS — MVP 关键设计取舍

## D-001 不做“大而全 Excel Agent”

原因：

通用 Excel 分析能力已经高度成熟，直接竞争缺乏差异化。

选择：

聚焦“两份数据为什么对不上”。

---

## D-002 确定性计算不交给 LLM

原因：

企业对账要求可重复、可验证。

选择：

Pandas / DuckDB 完成所有核心统计、Join 和 Diff。

---

## D-003 Mapping 不是黑盒

原因：

字段映射错误会污染后续全部结果。

选择：

每条 Mapping 都包含 confidence + reasons。

---

## D-004 Enum Mapping 默认需要确认

原因：

`1`、`ACTIVE`、`SUCCESS` 等值依赖企业业务语义，不能凭常识推断。

---

## D-005 Fact 与 Hypothesis 分离

原因：

发现“18 个缺失记录都是 CANCELLED”只能说明模式，不能证明目标系统存在过滤规则。

---

## D-006 本地优先

原因：

企业数据可能涉及客户、订单、金额和账号信息。

选择：

文件默认本地处理；仅必要的脱敏元数据允许进入外部模型。

---

## D-007 MVP 不做 Connector

原因：

Connector 增加集成成本，但不能验证用户是否真的需要对账 Workflow。

等产品验证成功后再做。
