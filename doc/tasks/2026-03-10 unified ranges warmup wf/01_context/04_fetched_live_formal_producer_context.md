# Fetched / Live Formal Producer 背景与取舍

## 1. 背景

`03-10` 定义统一 `ranges / warmup / mapping / WF` 真值链。fetched / live 数据入口是 formal `DataPack` 的 producer，必须交付符合这条真值链的 full pack。

这个 producer 的设计边界是：

1. Rust planner 负责 warmup、coverage、range 与 `DataPack` 初始构建真值。
2. Python 负责网络请求、响应转换与 runner 编排。
3. `WF` 消费 formal full `DataPack`，不补写 producer 语义。
4. 参数集合会影响 required warmup，因此数据规划必须基于当前运行实际使用的参数。

这个边界使 fetched / live formal path 与 direct / simulated 低层 builder path 保持分工清楚：前者必须经过 planner lifecycle，后者可以继续作为受控工具入口存在。

## 2. Coverage-Only Producer 不是正式方案

coverage-only producer 的核心形态是：

1. Python 先请求 base 数据。
2. Python 对非 base source 做 coverage-only backfill。
3. 最后直接调用 `build_time_mapping(...)`。

这条路径不能作为 fetched / live formal producer：

1. `build_time_mapping(...)` 最终走 `build_full_data_pack(...)`。
2. `build_full_data_pack(...)` 会把每个 source 的 `ranges` 写成 `0 / height / height`。
3. 这种 range 只能表达“整包都是 active”，不能表达 `base_first_live_time` 左侧的 per-source warmup。
4. 多周期场景下，非 base source 可能在 base 首个 live 附近根本没有足够 warmup。

正式方案必须让 `planner.finish()` 成为 fetched / live formal full `DataPack` 的出口。Python 不能在 planner 之外自行重建 `ranges`，也不能把 coverage 成立误当成 warmup contract 成立。

## 3. 为什么归属 `03-10`

以下三件事属于同一个 `03-10` contract：

1. fetched / live formal producer 没有完整接入 planner lifecycle。
2. `WF` 入口缺少 readiness guard，导致 producer gap 暴露太晚。
3. producer 编排顺序需要改为先冻结策略参数，再规划数据请求。

若拆成独立 task，会把 `03-10` 的 warmup / ranges contract 切散。更清晰的归属是把它们作为 `03-10` 当前正式范围的一部分，由同一组 context / spec / execution 文档承载。

## 4. 关键取舍

### 4.1 Producer 修复优先

真正修复必须发生在 producer：

1. fetched / live formal path 必须走 `DataPackFetchPlanner::new(...)`。
2. Python 只执行网络请求和响应转换。
3. `planner.finish()` 是 formal full `DataPack` 的唯一出口。

`WF` guard 只能提前暴露输入不满足 contract，不能修补 `DataPack`。这可以避免把 producer 错误推迟到窗口投影、指标计算或信号阶段才暴露。

### 4.2 参数先冻结

planner 需要 `indicators_params` 和 `backtest_params` 来计算 `required_warmup_by_key`。

因此 fetched / live formal producer 不能先构建数据，再构造运行参数。它必须拿到当前运行会使用的 `SingleParamSet` 后，才能规划请求。

这会影响 `params_override`、优化、敏感性分析、批量运行等入口。任何会改变 warmup contract 的参数集合，都不能静默复用按另一组参数规划出来的 fetched `DataPack`。

### 4.3 WF guard 只做入口断言

`WF` guard 应该在 `run_walk_forward(...)` 入口前移错误，但不能成为通用 `DataPack` validator。

guard 的判断锚点必须来自 WF 第 0 窗的 active 起点，而不是无条件使用 `data.ranges[base].warmup_bars`。原因是 direct / simulated `DataPack` 可以拥有 `ranges[base].warmup_bars = 0`，但仍然在第 0 窗 active 起点具备足够 left context。

### 4.4 范围外

以下问题不进入 `03-10`：

1. HA、typical price、returns 等派生结果建模。
2. `DataPack.source` 是否全局只允许 `ohlcv_*` raw source。
3. Python 外部指标注入接口。
4. Rust / Python 指标结果合并接口。
5. signal 文本引用指标列的语义调整。

这些问题已沉淀到 [TODO_raw_source_boundary_and_external_indicators.md](/home/hxse/pyo3-quant/doc/todo/TODO_raw_source_boundary_and_external_indicators.md)。
