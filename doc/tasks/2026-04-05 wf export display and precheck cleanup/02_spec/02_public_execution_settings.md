# 公开执行边界与设置契约

## 1. PyO3 暴露边界

### 1.1 暴露给 PyO3 的正式对象

下面这些对象属于正式 PyO3 暴露面：

1. `ExecutionStage`
2. `ArtifactRetention`
3. `SettingContainer`
4. `DataPack`
5. `SingleParamSet`
6. `TemplateContainer`
7. `ResultPack`
8. `OptimizationResult`
9. `WalkForwardResult`
10. `SensitivityResult`

本次任务没有新增独立的模式入口对象。

新增对外可见的只有 `SettingContainer.artifact_retention` 这一字段及其枚举类型 `ArtifactRetention`。

`SettingContainer` 作为公开执行设置对象暴露，字段固定为 `stop_stage / artifact_retention`。

`DataPack` 与 `ResultPack` 作为公开输入 / 输出类型存在，但它们不属于 Python 侧自由构造对象：

1. Python stubs 不公开 `DataPack.__new__` 与 `ResultPack.__new__`
2. Python stubs 不公开 pack setter
3. Python 侧只能通过 producer 真值入口体系获得 pack object
4. 这里的 producer 真值入口体系，包含 `02_spec/01_pack_producer_contracts.md` 中冻结的 producer 真值入口本体，以及闭集 formal delegator
5. Rust 生产代码同样只能通过 producer 真值入口体系产出 pack，不允许绕过工具函数直接手造正式 pack object

### 1.2 不暴露给 PyO3 的内部对象

下面这些对象只属于 Rust 内部执行层：

1. `PipelineRequest`
2. `PipelineOutput`
3. `execute_single_pipeline(...)`
4. `evaluate_param_set(...)`

它们不进入 Python stubs，也不作为公开 API 参数或返回值。

### 1.3 命名分层

执行层命名分层固定为：

1. Rust 正式模式入口：`run_*`
2. Rust PyO3 wrapper：`py_run_*`
3. Rust 内部执行器：`execute_*`
4. Rust 内部样本评估：`evaluate_*`
5. `replay` 只表示 WF 内部步骤概念，不单独承诺 `replay_*` helper 命名；若实现里出现 `replay_*`，只视为局部 helper，不构成新的正式层级

`py_run_*` 只是绑定层符号，不承担业务语义。

### 1.4 公开 backtest 入口命名

正式 backtest 模式入口命名固定为：

1. single：`run_single_backtest(...)`
2. batch：`run_batch_backtest(...)`

对应的 PyO3 wrapper 固定为：

1. `py_run_single_backtest(...)`
2. `py_run_batch_backtest(...)`

## 2. 公开执行设置契约

公开执行设置对象为：

```text
SettingContainer {
    stop_stage: ExecutionStage,
    artifact_retention: ArtifactRetention,
}
```

其中：

```text
ExecutionStage = Indicator | Signals | Backtest | Performance
ArtifactRetention = AllCompletedStages | StopStageOnly
```

`ExecutionStage` 表示公开 stop 边界。

`ArtifactRetention` 表示公开结果中保留哪些已完成阶段产物。

## 3. 公开设置组合与公开结果矩阵

本节与 [03_pipeline_request_and_output_contracts.md](./03_pipeline_request_and_output_contracts.md) 第 3 节中的“公开设置到内部请求的编译矩阵”描述的是同一组 `SettingContainer { stop_stage, artifact_retention }` 组合。

区别只在于：

1. 本节定义这些公开组合最终必须呈现什么公开结果
2. 后一节定义这些公开组合在内部必须被编译成哪个 `PipelineRequest`

两张表必须一一对应，不允许出现公开层和内部层各写一套语义。

single / batch 模式按下面的矩阵返回公开结果：

1. `SettingContainer { stop_stage: Indicator, artifact_retention: AllCompletedStages }`：只返回 indicators
2. `SettingContainer { stop_stage: Indicator, artifact_retention: StopStageOnly }`：只返回 indicators
3. `SettingContainer { stop_stage: Signals, artifact_retention: AllCompletedStages }`：返回 indicators 与 signals
4. `SettingContainer { stop_stage: Signals, artifact_retention: StopStageOnly }`：只返回 signals
5. `SettingContainer { stop_stage: Backtest, artifact_retention: AllCompletedStages }`：返回 indicators、signals、backtest
6. `SettingContainer { stop_stage: Backtest, artifact_retention: StopStageOnly }`：只返回 backtest
7. `SettingContainer { stop_stage: Performance, artifact_retention: AllCompletedStages }`：返回 indicators、signals、backtest、performance
8. `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }`：只返回 performance

`mapping`、`ranges`、`base_data_key` 始终保留在公开结果中。
