# 内部 Pipeline 模式与失败语义契约

## 1. 合法性分层

执行层合法性分成三层：

1. pack producer 真值入口约束：
   `DataPack` / `ResultPack` 的对象合法性由 producer 真值入口保证。
2. 执行器合法性校验：
   只检查 `PipelineRequest` 与 `PipelineOutput` 涉及的数据形状是否合法，例如 raw indicators 不带 `time`、各阶段高度一致。
3. 阶段局部校验：
   参数与运行时约束由真正消费它们的阶段模块负责。

固定边界如下：

1. pack object 真值不由 `run_*` 入口共享 guard 承担。
2. 执行器只消费已经成形的 `PipelineRequest`。
3. 执行器合法性校验不替代阶段局部校验。
4. Python precheck 不构成第二套 gate。

## 2. 内部执行器与公开结果边界

正式内部执行器为：

```text
execute_single_pipeline(
    data,
    param,
    template,
    request,
) -> Result<PipelineOutput, QuantError>
```

底层 `ResultPack` producer 为：

```text
build_result_pack(
    data,
    indicators,
    signals,
    backtest,
    performance,
) -> ResultPack
```

`PipelineOutput -> ResultPack` 的公开边界 wrapper 为：

```text
build_public_result_pack(
    data,
    output,
) -> ResultPack
```

边界固定为：

1. `execute_single_pipeline(...)` 返回 `PipelineOutput`。
2. `build_result_pack(...)` 是唯一底层允许给 raw indicators 补 `time` 列的 producer 边界。
3. `build_public_result_pack(...)` 只负责把严格 `PipelineOutput` 翻译成对底层 `build_result_pack(...)` 的调用。
4. Rust 内部凡是需要 single pipeline 语义的路径，都通过 `execute_single_pipeline(...)` 推进。

## 3. single / batch 模式契约

single / batch 的业务入口语义固定为：

1. `run_single_backtest(...) -> ResultPack`
2. `run_batch_backtest(...) -> Vec<ResultPack>`

这两个入口都完整消费 `SettingContainer` 的公开语义：

1. `stop_stage` 决定公开结果停在哪一层。
2. `artifact_retention` 决定公开结果保留哪些已完成阶段产物。
3. 入口先把 `SettingContainer` 编译成严格 `PipelineRequest`。
4. 内部执行器返回 `PipelineOutput`。
5. 公开边界通过 `build_public_result_pack(...)` 构建 `ResultPack`。

两者区别只在最外层组织形式：

1. `run_single_backtest(...)` 返回单个 `ResultPack`。
2. `run_batch_backtest(...)` 返回 `Vec<ResultPack>`。
3. 内部单次 pipeline 语义与阶段编排真值完全共用。

## 4. walk-forward 模式契约

`run_walk_forward(...)` 的公开模式是完整 WF 结果模式。

它要求：

1. `stop_stage = Performance`
2. `artifact_retention = AllCompletedStages`

WF 内部子步骤固定为：

1. first evaluation：
   `ScratchToSignalsAllCompletedStages`
2. natural replay：
   `SignalsToBacktestStopStageOnly { signals }`
3. final window evaluation：
   `SignalsToPerformanceAllCompletedStages { indicators_raw, signals }`
4. stitched performance consolidation：
   `BacktestToPerformanceAllCompletedStages { indicators_raw, signals, backtest }`

## 5. optimizer / sensitivity 模式契约

`run_optimization(...)` 与 `run_sensitivity_test(...)` 的公开模式都是 performance 评估模式。

它们要求：

1. `stop_stage = Performance`
2. `artifact_retention = StopStageOnly`

这两个模式共享一套样本评估 helper：

```text
evaluate_param_set(
    data,
    param,
    template,
) -> Result<PerformanceMetrics, QuantError>
```

`evaluate_param_set(...)` 内部固定等价于：

```text
ScratchToPerformanceStopStageOnly
```

## 6. 失败语义

1. mode 入口若收到不满足本模式契约的 `SettingContainer`，模式立即失败。
2. 任一 `PipelineRequest` 若缺少其所要求的最小输入链，执行立即失败。
3. 任一 `PipelineRequest` 若携带本变体不允许的上游阶段输入，执行立即失败。
4. `SignalsTo*` / `BacktestTo*` 若传入带 `time` 列的 indicators，执行立即失败。
5. 任一请求若返回的 `PipelineOutput` 不匹配该请求的固定输出 shape，执行立即失败。
6. 内部执行器不接受通过公开 `ResultPack` 倒灌执行状态。
