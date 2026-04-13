# Python Runner View / Bundle 正式契约

## 1. 本文冻结什么

本文只冻结 Python runner wrapper 层的正式对象分层：

1. `Backtest` 门面返回哪些正式 view 对象
2. `RunnerSession` 的正式职责
3. 各类 view 的正式命名与边界
4. `PreparedExportBundle` 的正式职责

本文不重复 Rust 类型本身的对象 contract，也不重写 export payload 的 Zip 路径细节。

## 2. `Backtest` 的正式返回对象

`Backtest` 保留为 Python 执行门面。

它的正式返回对象固定为：

1. `Backtest.run() -> SingleBacktestView`
2. `Backtest.batch() -> BatchBacktestView`
3. `Backtest.walk_forward() -> WalkForwardView`
4. `Backtest.optimize() -> OptimizationView`
5. `Backtest.sensitivity() -> SensitivityView`
6. `Backtest.optimize_with_optuna() -> OptunaOptimizationView`

本任务不把 `Backtest` 门面名改成其他词。

`Backtest` 门面负责把模式方法编译成 Rust mode contract 要求的正式 `SettingContainer`：

1. `Backtest.run()` 与 `Backtest.batch()` 使用实例持有的 `engine_settings`，用于显式验证公开 execution setting 矩阵。
2. `Backtest.walk_forward()` 固定使用 `SettingContainer { stop_stage: Performance, artifact_retention: AllCompletedStages }` 调用 Rust WF 入口。
3. `Backtest.optimize()` 固定使用 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }` 调用 Rust optimizer 入口。
4. `Backtest.sensitivity()` 固定使用 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }` 调用 Rust sensitivity 入口。
5. `Backtest.optimize_with_optuna()` 固定使用 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }` 执行所有 Optuna trial。
6. 各 view 的 `session.engine_settings` 记录本次 view 实际执行使用的 mode setting 快照，而不是无条件复制或引用 `Backtest.engine_settings`。

这里不存在旧兼容或 fallback：Python 门面是公开易用入口，Rust mode guard 是核心执行入口的硬约束；二者之间的转换必须是唯一、显式、固定的。

## 3. `RunnerSession`

Python runner 的共享运行上下文正式收口为：

```text
RunnerSession {
    data_pack,
    template_config,
    engine_settings,
    enable_timing,
}
```

它的职责只有：

1. 保存各类 view 共同依赖的执行上下文
2. 以结构化字段承载共享运行上下文

`RunnerSession` 不承担执行逻辑、导出逻辑或 display 逻辑。

`RunnerSession.engine_settings` 是执行时快照。创建 view 后若再修改 `Backtest.engine_settings`，不得反向改变已经返回的 view 或导出 bundle 解释层。

## 4. 正式 view 集合

Python 结果层正式对象集合固定为：

1. `SingleBacktestView`
2. `BatchBacktestView`
3. `WalkForwardView`
4. `OptimizationView`
5. `SensitivityView`
6. `OptunaOptimizationView`

这组名字构成正式公开命名集合。

## 5. view 的统一规则

所有正式 view 都满足下面规则：

1. 它们表达的是结果语义，不是导出会话。
2. 它们可以暴露 `raw` 以及面向该模式的只读语义属性。
3. 它们统一提供 `build_report()` 与 `print_report()`。
4. 它们统一暴露 `session: RunnerSession` 作为共享运行上下文对象。
5. `session` 承载 `data_pack / template_config / engine_settings / enable_timing`。
6. 它们不保存 `export_buffers`、`export_zip_buffer` 一类导出缓存。
7. 它们不通过 `__getattr__` 无边界透传原始对象。

## 6. 各 view 的正式边界

### 6.1 `SingleBacktestView`

它表达 single backtest 的正式结果视图。

正式字段语义为：

1. `raw` 对应单个 `ResultPack`
2. `params` 对应本次 single 执行使用的 `SingleParamSet`
3. `session` 对应 `RunnerSession`

### 6.2 `BatchBacktestView`

它表达 batch backtest 的正式集合视图。

正式职责为：

1. 表达一组 single 结果
2. 暴露 batch 级只读结果语义
3. `session` 对应 `RunnerSession`

本任务不冻结 `BatchBacktestView.select(...)` / `best_by(...)` 这类 convenience helper。

原因是当前仓库没有稳定的正式使用面依赖它们，把它们提前冻结成正式 API 只会扩大公开契约面。

`BatchBacktestView` 本身不直接提供导出入口。

### 6.3 `WalkForwardView`

它表达 WF 的正式结果视图。

正式字段语义为：

1. `raw` 对应 `WalkForwardResult`
2. `stitched_result` 对应 stitched artifact
3. `window_results` 对应窗口结果数组
4. `session` 对应 `RunnerSession`

`WalkForwardView` 不暴露 `run_result` 代理，不伪造 single 结果视图。

### 6.4 `OptimizationView` / `SensitivityView` / `OptunaOptimizationView`

它们分别表达 optimization、sensitivity、optuna optimization 的正式结果视图。

这三类 view 统一满足：

1. 暴露 `raw`
2. 暴露模式专属的只读语义属性
3. 暴露 `build_report()` / `print_report()`
4. 不额外承担导出或 display 职责

## 7. 正式导出入口

只有下面两类 view 具备正式导出入口：

1. `SingleBacktestView`
2. `WalkForwardView`

这是从当前正式使用场景出发的硬约束，不是“其他 view 先不写，未来再模糊补上”。

理由如下：

1. single 与 WF stitched 当前都存在正式的 chart / bundle / display 消费链。
2. `BatchBacktestView` 的正式语义是“single 结果集合”，不是单一 bundle 解释对象；如果未来要为它补正式选择 helper 或单项导出路径，应在新 task 中单独冻结对应 contract。
3. `OptimizationView`、`SensitivityView`、`OptunaOptimizationView` 当前正式语义都是研究 / 汇总 /评估结果视图，不进入现有 chart bundle 消费链。
4. 如果在没有真实消费场景的前提下给全部 view 统一加 `prepare_export(...)`，只会把接口做虚，重新引入“每个 view 都好像能导出，但其实语义不同”的歧义。

因此本任务的正式口径是：

1. 只有 `SingleBacktestView` 与 `WalkForwardView` 具备正式导出能力。
2. 其他 view 不定义 `prepare_export(...)`。
3. 若未来确实出现新的正式导出场景，应在新 task 中显式补充对应 adapter、payload contract 和 bundle 消费面，而不是在这次 task 中预留空接口。

它们的正式导出方法固定为：

```text
prepare_export(config) -> PreparedExportBundle
```

`prepare_export(...)` 的正式语义是：

1. 它是纯投影调用
2. 它不修改 view 自身状态
3. 它内部固定委托本 view 对应的 adapter 生成 `ExportPayload`
4. 它再通过 packager 生成 `PreparedExportBundle`

`format_for_export(...)` 不是正式命名。

这里不存在额外一层“动态选择 adapter”的开放语义。

正式绑定关系固定为：

1. `SingleBacktestView.prepare_export(...) -> single adapter`
2. `WalkForwardView.prepare_export(...) -> WF adapter`

若后续出现新的可导出 view，也必须在 spec 中显式补充它固定绑定哪个 adapter，不允许把“按类型猜 adapter”写成隐式约定。

## 8. `PreparedExportBundle`

导出会话层的正式对象为：

```text
PreparedExportBundle {
    buffers,
    zip_buffer,
    chart_config,
}
```

它的正式职责只有：

1. 作为 display 的正式输入
2. 作为 save 的正式输入
3. 作为 upload 的正式输入
4. 作为导出链路的唯一缓存对象

因此正式方法固定为：

1. `display(...)`
2. `save(...)`
3. `upload(...)`

这三个方法不挂在 view 上。

## 9. display 层的正式输入

`py_entry/runner/display/` 的正式输入类型是 `PreparedExportBundle`。

display 层不直接消费：

1. `SingleBacktestView`
2. `WalkForwardView`
3. `ResultPack`
4. `WalkForwardResult`

## 10. 禁止事项

1. 禁止在 `WalkForwardView` 中惰性拼 single 结果代理。
2. 禁止用 best-window params 伪装 stitched single 结果语义。
3. 禁止使用 `context: dict` 承接共享运行上下文。
4. 禁止在 view 上缓存导出副作用状态。
5. 禁止在正式公开命名里保留 `Wrapper` 后缀。
