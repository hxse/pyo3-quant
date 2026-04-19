# TODO: Raw Source 边界与外部指标注入

> 本文档是未来计划备忘，不是当前 Task Spec。
>
> 关联背景：
>
> * `doc/tasks/2026-03-10 unified ranges warmup wf/01_context/04_fetched_live_formal_producer_context.md`
> * `doc/tasks/2026-03-10 unified ranges warmup wf/02_spec/06_fetched_live_formal_producer_and_wf_readiness.md`

## 1. 背景

`03-10` 当前正式范围聚焦 fetched / live formal producer、planner lifecycle、`WF` readiness guard、策略参数冻结顺序。

讨论过程中发现两个相关但不应塞进 `03-10` 的未来问题：

1. `DataPack.source` 是否应该全局强约束为只承载 `ohlcv_*` raw source。
2. Python 侧外部指标、HA、typical price、returns 等派生结果未来是否应该通过指标阶段合并进 `IndicatorResults`。

这两个问题本质上都在定义输入事实与计算产物的边界：

1. `DataPack.source` 更适合表达原始市场输入。
2. `ResultPack.indicators` / `IndicatorResults` 更适合表达计算结果。

## 2. 初步判断

当前倾向是：

1. `DataPack.source` 只放 raw market source。
2. 当前项目的 raw market source 主要是 `ohlcv_*`。
3. HA、typical price、returns、Python 自定义特征等派生结果不应作为新的 `source_key` 塞进 `DataPack.source`。
4. 派生结果未来更适合作为 `IndicatorResults[source_key]` 下的列存在。
5. 外部指标注入应发生在指标阶段之后、信号阶段之前，而不是在 `build_result_pack(...)` 导出阶段才合并。

一个更干净的未来形态是：

```text
DataPack.source["ohlcv_1h"]
IndicatorResults["ohlcv_1h"]:
  ha_open
  ha_high
  ha_low
  ha_close
  sma_20
  rsi_14
```

而不是：

```text
DataPack.source["ha_1h"]
```

## 3. 未来需要解决的问题

### 3.1 Raw Source 边界

需要决定并落地：

1. `DataPack.source` 是否全局只接受 `ohlcv_*`。
2. `base_data_key` 是否必须是 `ohlcv_*`。
3. `build_data_pack(...)`、`build_time_mapping(...)`、`build_mapping_frame(...)` 是否都要拒绝非 raw source key。
4. 当前 `OtherParams.ha_timeframes` 向 `source_dict` 注入 `ha_*` 的旧路径如何清理。
5. 测试和文档中关于 `ha_*` 作为 source 的旧口径如何迁移。

这属于 breaking contract cleanup，应单独开 task，不应作为 `03-10` 的附带改动。

### 3.2 外部指标注入

需要设计一个明确接口，让 Python 侧可以提供外部指标结果，并在指标阶段与 Rust 内置指标合并。

未来接口需要冻结以下 contract：

1. 外部指标必须按现有 `DataPack.source` key 分组，例如 `ohlcv_1h`。
2. 外部指标 DataFrame 不携带 `time` 列，时间列由 result builder 或统一 helper 从 source attach。
3. 外部指标高度必须等于对应 `DataPack.source[source_key]` 的高度。
4. 外部指标列名不得与 Rust 内置指标列名冲突，冲突直接 fail-fast。
5. 若外部指标参与信号生成，合并必须发生在 signal stage 之前。
6. 若外部指标需要 warmup，必须有独立 warmup 声明，并进入 planner 的 `required_warmup_by_key` 聚合。
7. 外部指标进入回测主链后，必须由 Rust 回测引擎内部统一校验；Python 侧可以做辅助预检，但不能成为唯一校验层。

Rust 内部校验至少应覆盖：

1. `source_key` 必须存在于 `DataPack.source`。
2. DataFrame 不允许携带 `time` 列。
3. DataFrame 高度必须等于对应 source 高度。
4. 所有列名必须非空、唯一，且不得与 Rust 内置指标结果冲突。
5. 列 dtype 必须属于信号解析和导出链路支持的类型集合。
6. 指标列不得包含会破坏信号比较语义的非法值；允许的 null / NaN 策略必须在正式 task 中冻结。
7. 声明的 warmup 必须能并入 `required_warmup_by_key`，缺失声明时不得让外部指标影响 signal。

## 4. 与 `03-10` 的边界

`03-10` 当前正式范围不处理本文问题。

`03-10` 只负责：

1. fetched / live formal producer 接回 `DataPackFetchPlanner` lifecycle。
2. 策略参数先冻结，再规划数据请求。
3. `WF` 入口验证 full `DataPack` 是否满足 `required_warmup_by_key`。

本文问题留给未来独立 task。未来 task 可以命名为：

```text
2026-xx-xx raw source boundary and external indicators
```

## 5. 暂定非目标

未来 task 也不应把问题扩大成通用特征平台。

暂定非目标：

1. 不做任意 feature store。
2. 不做跨 symbol / 跨市场数据融合。
3. 不让 `DataPack.source` 混入任意 Python 计算产物。
4. 不让 `build_result_pack(...)` 承担 signal 前的指标合并职责。
5. 不在没有 warmup contract 的情况下允许外部指标影响信号。

## 6. 初步收口方向

未来更合理的收口方向是：

1. `DataPack.source` 收口为 raw source container。
2. 派生产物统一进入 `IndicatorResults`。
3. Python 外部指标通过独立 pipeline 输入进入指标阶段。
4. Rust 负责校验外部指标的 key、高度、time 列、列名冲突和 warmup 声明。
5. `WF` 不理解外部指标来源，只消费已经符合 contract 的 `DataPack`、`IndicatorResults`、signals 和 backtest output。
