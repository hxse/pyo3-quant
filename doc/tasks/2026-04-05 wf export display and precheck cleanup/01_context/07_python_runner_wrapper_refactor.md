# Python Runner Wrapper 为什么要整体重构

## 1. 这次要收的不只是 `RunResult`

当前 `py_entry/runner` 的问题不是单个类命名不佳，而是整层没有统一模型。

现在至少混着 4 种风格：

1. `RunResult`：single 结果视图 + 导出副本构造 + bundle 缓存 + display/save/upload。
2. `WalkForwardResultWrapper`：Rust 原始结果 + stitched single 结果代理。
3. `BatchResult`：结果数组 + 参数数组 + `context: dict`，再临时拼回 `RunResult`。
4. `OptimizeResult` / `SensitivityResultWrapper` / `OptunaOptResult`：分别使用 `Result / Wrapper / OptResult` 三套命名和职责风格。

这说明问题不是边角兼容，而是 Python wrapper 层本身没有收口。

## 2. 只清边界不够

这里至少有过三种可选路径：

1. 只清 `RunResult` 和 `WalkForwardResultWrapper` 的导出边界。
2. 保留 `results/` 目录和现有对象名，只把 bundle 会话拆出去。
3. 直接把 Python wrapper 层重构成统一模型。

前两种都不够好。

原因是：

1. 它们仍然默认 `RunResult` 是中心对象，只是在它周围挪字段。
2. `BatchResult`、`SensitivityResultWrapper`、`OptunaOptResult` 的命名和职责分裂不会被一起解决。
3. `context: dict`、惰性代理、透传式 wrapper 这些低品味结构会继续保留。

## 3. 这次选择的方向

这次任务直接选择第三种：整体重构 Python wrapper 层。

正式目标只有 4 条：

1. 保留 `Backtest` 作为执行门面，不在这次任务里顺手改门面名。
2. Python 结果层收口为统一的 view 体系，不再混用 `Result / Wrapper / OptResult`。
3. 导出会话层收口为独立 bundle 对象，结果视图不再缓存导出副作用状态。
4. display/save/upload 只消费 bundle，不再消费结果视图。

## 4. 为什么这是更统一的结构

更优雅的 Python wrapper 应当拆成四层：

1. 门面层：`Backtest`
2. 共享会话层：`RunnerSession`
3. 结果视图层：`*View`
4. 导出会话层：`PreparedExportBundle`

这样分层后：

1. `Backtest` 只负责调 Rust 入口并返回正式 view。
2. `RunnerSession` 只保存 `data_pack / template_config / engine_settings / enable_timing` 这类共享运行上下文。
3. 各种结果视图只表达“结果是什么”，不再负责持久化缓存和展示副作用。
4. bundle 只表达“已经准备好的导出产物”，并成为 display/save/upload 的唯一输入。

## 5. 为什么 `WalkForwardResultWrapper` 不该继续保留

WF stitched 当前通过构造一个 stitched `RunResult` 来复用 single 的导出 / display。

这条路不够诚实：

1. stitched 结果不是 single 结果。
2. WF 的正式解释资产是 `backtest_schedule`，不是单一 `params`。
3. 继续保留这层代理，只会让 adapter 和 converter 持续背负兼容状态。

因此最终收口不是“给 `WalkForwardResultWrapper` 改个更好名字”，而是让 `WalkForwardView` 直接拥有自己的导出入口，并直接走 WF adapter。

## 6. 为什么 `RunResult` 也不该继续当中心对象

`RunResult` 当前的问题不是它属于 single，而是它承担了太多职责：

1. 它既是 single 结果视图。
2. 又负责导出副本构造。
3. 又负责 chart config 生成。
4. 又保存 `_export_buffers` / `_export_zip_buffer`。
5. 又负责 display/save/upload。

这会把“结果对象”和“导出会话对象”揉在一起。

更好的方向是：

1. `SingleBacktestView` 只表达 single 结果。
2. `PreparedExportBundle` 只表达导出会话和 bundle 产物。

## 7. 这次为什么要并进 `04-05`

这条线不属于顺手美化，而属于当前 task 的正式主线。

原因很直接：

1. 它和 export/display cleanup 是同一条调用链。
2. 它和 WF stitched 不再伪装 single 结果是同一个边界问题。
3. 它和 `_converters_bundle.py` 不再理解业务对象是同一个责任收口问题。
4. 如果这次不一起做，`04-05` 最后仍会留下 Python wrapper 这层双轨兼容壳。
