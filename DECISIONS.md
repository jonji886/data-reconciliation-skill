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

---

## D-008 严格解析失败进入 UNVERIFIED

原因：删除单位、币种、百分号或未知文本会把不同业务语义压成同一个
Decimal；日期解析失败后回退字符串比较也会产生相同风险。

选择：数值只接受严格数字、合法千位分隔和科学计数法，并使用 Decimal；
日期只接受无歧义格式。解析失败、NaN/Infinity、Boolean 数值和缺少时区
的混合比较进入独立 `UNVERIFIED` 状态，不进入 MATCH 或普通
`Value_Mismatch`。

兼容性：保留 `values_equal()` 的 `(bool, difference_type)` 返回接口；旧
调用会收到 `False` 和明确的 `UNVERIFIED_*` 类型，完整状态由内部结果和
报告传播。

---

## D-009 比较覆盖率必须显式可见

原因：枚举等高风险 Mapping 被安全跳过是正确行为，但“未比较”不能被
误读为“已一致”。

选择：记录 `COMPARED`、`UNMAPPED`、`PENDING_CONFIRMATION`、`SKIPPED`、
`UNSUPPORTED_RULE` 和 `UNVERIFIED` 字段状态；空规则和覆盖不完整的运行
统一标记 `PARTIAL_NEEDS_REVIEW`。单元格级未验证数量与字段级覆盖数量分开
统计。
