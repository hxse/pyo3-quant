# Fetched / Live Formal Producer 与 WF Readiness

## 1. 范围

本文定义 fetched / live formal producer、参数冻结顺序与 `WF` input readiness 的正式 contract。

范围内：

1. fetched / live formal `DataPack` producer。
2. 策略参数冻结与数据请求规划顺序。
3. `WF` input readiness guard。
4. indicator source subset 入口校验。
5. coverage-only 旧路径的 formal 语义边界。

范围外：

1. HA、typical price、returns 等派生产物建模。
2. `DataPack.source` 的 `ohlcv_*` 全局强约束。
3. Python 外部指标注入。
4. 指标结果合并接口。

## 2. Fetched / Live Producer Contract

fetched / live formal `DataPack` producer 必须走 `DataPackFetchPlanner` lifecycle。

正式流程：

```text
freeze SingleParamSet
build DataPackFetchPlannerInput
planner = DataPackFetchPlanner(input)

while planner.next_request() exists:
    request = planner.next_request()
    df = Python fetch(request)
    planner.ingest_response(request, df)

data_pack = planner.finish()
```

约束：

1. Python 只负责网络 IO、`OhlcvRequestParams` 组装、响应到 `pl.DataFrame` 的转换。
2. Python 不计算 warmup、不判断 head warmup、不计算 `ranges`。
3. `planner.finish()` 是 fetched / live formal full `DataPack` 的唯一正式出口。
4. fetched / live formal path 不允许在 planner 后再调用 `build_time_mapping(...)` 重建 full pack。
5. `build_time_mapping(...)` 只作为 direct / simulated / 低层工具入口存在，不承担 fetched / live formal producer 语义。

## 3. Planner Input Contract

`DataPackFetchPlannerInput` 必须来自已冻结的运行参数与显式取数配置。

字段来源：

1. `timeframes` 来自 `OhlcvDataFetchConfig.timeframes`。
2. `base_data_key` 来自 `OhlcvDataFetchConfig.base_data_key`。
3. `effective_since` 来自 `OhlcvDataFetchConfig.since`。
4. `effective_limit` 来自 `OhlcvDataFetchConfig.limit`。
5. `indicators_params` 来自当前运行使用的 `SingleParamSet.indicators`。
6. `backtest_params` 来自当前运行使用的 `SingleParamSet.backtest`。

失败语义：

1. `since=None` 在 formal fetched planner path 中非法，必须 fail-fast。
2. `limit=None` 在 formal fetched planner path 中非法，必须 fail-fast。
3. `effective_limit < 1` 必须 fail-fast。
4. `OhlcvDataFetchConfig.align_to_base_range=True` 不属于 formal planner path；若传入，必须 fail-fast 或先在执行计划中明确迁移策略。

## 4. 参数冻结 Contract

fetched / live producer 必须先确定当前运行会使用的 `SingleParamSet`，再规划数据请求。

各入口约束：

1. `run(...)` 使用 `params_override` 时，data planning 必须使用 override 后参数。
2. `walk_forward(...)` 使用 `params_override` 时，data planning 必须使用 override 后参数。
3. `optimize(...)` / `sensitivity(...)` 的 planning 参数必须覆盖该模式可能使用的最坏 warmup；对 `optimize=true` 的 warmup 相关字段，仍按 helper 内部 `Param.max` 规则解析。
4. `batch(...)` 若参数列表可能拥有不同 warmup contract，必须基于参数列表聚合后的最大 warmup 规划数据，或直接拒绝不满足已规划 warmup 的参数列表。

复用限制：

1. 一个 fetched `DataPack` 只能被声明为满足其 planning 参数对应的 warmup contract。
2. 后续入口若传入会扩大 warmup contract 的 `params_override`，不得静默复用旧 `DataPack`。
3. 合法实现可以选择重新规划并重建 `DataPack`，也可以选择 fail-fast；不能静默继续。

## 5. WF Readiness Guard Contract

`WF` 入口必须在窗口规划前做 input readiness guard。

位置：

```text
validate_mode_settings(...)
build_warmup_requirements(...)
validate_indicator_source_subset(...)
validate_wf_input_datapack_readiness(...)
build_window_indices(...)
```

职责：

1. 只服务 `walk_forward`。
2. 只提前判断输入 full `DataPack` 是否具备第 0 窗基础 warmup 条件。
3. 不修改 `DataPack`。
4. 不修补 `ranges`。
5. 不替代 planner producer 修复。
6. 不承担 `min_warmup_bars` 之外的窗口几何判断。

## 6. WF Guard 锚点

guard 的锚点来自 WF 第 0 窗 active 起点，而不是无条件来自 `data.ranges[base].warmup_bars`。

计算步骤：

1. `base_required = required_warmup_by_key[base]`。
2. `train_warmup = max(base_required, config.min_warmup_bars)`。
3. `test_warmup = max(base_required, config.min_warmup_bars, 1)`。
4. `train_active_start = train_warmup`。
5. `train_active_end = train_active_start + config.train_active_bars`。
6. `test_active_start`：
   - `BorrowFromTrain`: `train_active_end`
   - `ExtendTest`: `train_active_end + test_warmup`

必须校验的 base anchors：

1. `train_active_start`
2. `test_active_start`

任一 anchor 越过 base source 高度，直接报错。

## 7. WF Guard Source-Level 校验

对每个 source `k`，在每个 anchor row 上校验：

1. `data.source[k]` 必须存在。
2. `data.mapping[k]` 必须存在。
3. `data.mapping[k][anchor]` 必须存在且非 null。
4. `mapped_src_idx >= required_warmup_by_key[k]`。

对 base source，校验退化为：

```text
anchor >= required_warmup_by_key[base]
```

错误信息必须包含：

1. `source_key`
2. `anchor_base_row`
3. `mapped_src_idx`
4. `required_warmup`
5. `run_walk_forward(...)` 入口语境

错误口径必须指向：

```text
WF 输入 full DataPack 不满足 required_warmup_by_key
```

## 8. Indicator Source Subset Contract

`run_walk_forward(...)` 在 warmup 与 window planning 前必须校验：

```text
param.indicators.keys() ⊆ data_pack.source.keys()
```

约束：

1. 该校验不受 `ignore_indicator_warmup` 影响。
2. 即使忽略指标 warmup，指标本身仍会在窗口执行阶段被计算。
3. 任一指标 source 不存在时，必须在 `run_walk_forward(...)` 入口 fail-fast。

## 9. Coverage-Only Path Contract

以下行为不承担 fetched / live formal full pack 语义：

1. Python `_fetch_with_coverage_backfill(...)`。
2. fetched branch 先拼 `source_dict` 再调用 `build_time_mapping(...)`。
3. `build_full_data_pack(...)` 为所有 source 写 `0 / height / height`。

迁移后：

1. `end_backfill_min_step_bars` 不再驱动 formal fetched producer；若保留，只能服务旧工具路径或被删除。
2. synthetic all-false `skip_mask` 不再是 fetched planner finish 的必要产物；没有真实 skip 信息时使用 `None`。
3. direct / simulated 路径可继续使用低层 builder，但不得被描述成 fetched / live formal planner path。
