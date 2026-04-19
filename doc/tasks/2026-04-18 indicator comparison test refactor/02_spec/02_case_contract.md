# Case Contract

## 1. Case 定义

每个指标比较 case 是一个最小可执行校验声明。

case 不负责让程序推断 oracle 优先级。用户在 case 中直接声明主校验源，程序只执行。

case 必须描述：

1. `id`
2. `indicator_base_name`
3. `indicator_key`
4. `source_key`
5. `dataset_source`
6. `params`
7. `outputs`
8. `primary_validation_source`
9. `secondary_oracle_assertions`
10. `tolerance_policy`
11. `skip_policy`
12. `warmup_check`

## 2. 强类型约束

正式落地时，case、adapter、oracle、dataset、skip、tolerance 以及 adapter 回调的输入和返回，都必须使用 Pydantic 严格模型，并配合静态类型标注。

示例文档可以省略具体类型签名，但实现代码不得依赖裸 `dict` 在模块边界之间传递未校验结构。

强类型约束必须能通过 `just check` 的静态检查，并通过 `just test` 的测试验证。

## 3. 输出列解析

单输出指标的 engine 输出列默认是：

```text
<indicator_key>
```

多输出指标的 engine 输出列默认是：

```text
<indicator_key>_<suffix>
```

`outputs` 表达逻辑输出列名，例如 `lower / middle / upper`。

engine 输出列按本项目回测引擎默认输出格式解析。

oracle 输出列按对应 oracle 的默认返回格式解析，例如 pandas-ta 返回的默认列名。

解析方法写在该指标的 `adapter.py` 中，不在 case 里重复声明 engine / oracle 物理列名。

多输出指标一般必须覆盖全部正式输出列。若极特殊情况只覆盖部分列，在测试 case 附近用注释说明。

## 4. 参数表达

manifest 中参数统一使用普通值表达。

指标名、`indicator_key`、参数名默认使用本项目回测引擎的命名风格。

如果 pandas-ta 使用 `length`，而本项目回测引擎使用 `len`，manifest 前台应写 `len`。

执行时由测试框架统一转换：

1. 传给 engine 时，转换为本项目正式 `Param` / `IndicatorsParams` 格式。
2. 传给 pandas-ta / pandas-ta-classic 时，转换为对应函数的普通 kwargs。

不允许在测试框架中引入与 Rust 指标参数平行的第二套语义。

## 5. 数据集表达

每个 case 必须声明数据来源。

数据来源使用类型区分：

```python
dataset_source: DatasetId | Path
```

其中：

1. `DatasetId` 表示一个具体的标准生成数据集。
2. `Path` 表示一个本地 CSV 数据文件。

默认标准数据集复用当前项目数据生成能力：

```text
DataGenerationParams
generate_multi_timeframe_ohlcv(...)
```

测试层直接使用 `DataGenerationParams`，由项目数据生成链路调用 `generate_multi_timeframe_ohlcv(...)`。

`generate_ohlcv(...)` 是单周期子调用，不作为本任务标准测试入口。

标准生成数据集应通过不同 seed 与生成参数模拟真实 K 线波动，至少覆盖：

1. 默认随机 OHLCV。
2. 趋势或高波动 OHLCV。
3. 极端行情或短样本 OHLCV。

默认每个指标先固定 3 个标准 case，避免测试量过大。

这 3 个标准 case 的参数和 `DatasetId` 默认都应不同，用少量 case 同时覆盖参数变化和数据变化。

不要求同一参数组覆盖多个 `DatasetId`。

导出的 `CASES` 必须是 pytest 可直接参数化的最终 case 列表。

每个 dataset 必须对应一个独立 pytest item。

runner 只执行传入的单个 case，不得在单个 pytest case 内部再循环展开多个 dataset。

这样做的目的，是让 pytest 失败位置直接显示具体指标、参数和 dataset，而不是只显示某个 runner 内部循环失败。

本地 CSV 支持两种数据模式：

1. 自动生成数据：`dataset_source` 使用某个具体 `DatasetId`。
2. 本地加载数据：`dataset_source` 使用 `Path("fixtures/local_csv/custom_0.csv")`。

本地加载数据必须是 `Path` 类型，不能把 CSV 路径塞进字符串 group id。

本地 CSV 的相对 `Path` 默认相对当前指标目录解析。

`LocalCsvOracle` 不再重复声明 `path`；fixture 解析由 `dataset_source`、指标目录与 case id 的统一 resolver 处理。

本地 CSV 只需要预留 fixture 目录和统一读取入口，不替代标准生成数据集。

## 6. Pytest 输出

测试必须对 pytest 友好。

执行方式应优先使用 parametrized test，并提供清晰 `id`，使失败输出能直接看出：

1. 指标名。
2. 参数组。
3. 数据集。
4. 主校验源。
5. secondary assertion 类型。

禁止把大量 case 藏在一个 for-loop 里导致 pytest 只能显示单个测试失败。

禁止把多个 dataset 藏在同一个 pytest case 内部循环执行。

失败信息还必须满足 `10_failure_reporting_contract.md` 中的上下文要求。

## 7. Skip 与注释

本项目不提供静默跳过。

极特殊情况下需要跳过时，必须显式声明作用域：

1. `case`：跳过整个 case。
2. `output`：跳过指定输出列。

列级 skip 只影响指定列，其他输出列仍必须正常校验。

所有 skip 都必须使用 pytest 显式 skip 或 manifest skip 标记，并写明原因。

禁止通过注释删除 case 或输出列来隐藏跳过。

注释用于解释用户为什么选择某个主校验源、为什么某个 secondary assertion 期望 same 或 different、为什么某列需要特殊容差。

## 8. Warmup 关联

comparison case 与 warmup contract 不是同一个测试。

comparison case 不允许内联 `expected_bars`、`warmup_mode` 或类似 warmup 真值字段。

warmup 全局真值入口必须是 Rust `resolve_indicator_contracts(...)`。

warmup runner 复用 `cases.py` 中的 `CASES` 作为输入样本，不得另起一套 warmup 真值来源。

运行时输出校验必须消费聚合函数返回的 `contract.warmup_bars` 与 `contract.warmup_mode`。

新增或迁移指标时必须确认该指标已经进入 warmup 专用测试覆盖。

`IndicatorComparisonCase.warmup_check` 可以表达该 case 是否参与 warmup contract 校验，以及极特殊 skip 逃生舱。

`warmup_check` 不是 warmup 真值字段，不得包含 `warmup_bars`、`warmup_mode` 或类似真值。

warmup runner 复用 `cases.py` 中的 `CASES`，从同一份参数、source 与 dataset 派生 warmup 校验。

warmup 默认不可跳过。

允许保留跳过 warmup contract 的逃生舱，但只能通过 `WarmupCheck.skip(...)` 显式声明，且只由 warmup runner 消费。

若极特殊情况下需要跳过 warmup contract，必须使用显式 skip，并在注释中说明原因；AI 使用该能力前必须报告用户并讨论。

数值对齐 runner 不得消费 `warmup_check` 来改变数值对齐行为。

如果某个指标只迁移 comparison case，却丢失原有 warmup 静态契约、运行时输出契约或 scaling scan，视为重构漂移。
