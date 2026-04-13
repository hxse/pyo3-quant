# WF 导出与显示链路

## 1. 当前已经成立的事实

当前 notebook / display 路径真正需要的不是结果对象本身，而是一个已经成形的 bundle。

这说明：

1. display 的正式上游本来就是导出产物。
2. 真正需要统一的是 bundle 消费边界。
3. 不需要为了“统一使用体验”去强行统一结果解释层。
4. Python runner 的结果对象层与导出会话层应当拆开，而不是继续靠 `format_for_export(...)` 在结果对象上写缓存。

## 2. 当前实现为什么别扭

WF stitched 现在是先把 stitched 结果投影成一个带过渡字段的 single 结果视图，再复用 single 导出链路。

这会带来三件坏事：

1. `RunResult` 同时承载 single 语义和 WF 导出兼容语义。
2. `_converters_bundle.py` 被迫理解 `backtest_schedule`。
3. single / WF 的边界不再清楚，后续很容易继续堆字段。
4. Python wrapper 层会被迫把结果视图、bundle 会话和 display/save/upload 混在一个类里。

## 3. 本任务的选择

本任务不改前端消费协议，只改内部解释边界。

正式选择是：

1. single 和 WF 继续共享 display / bundle 消费链路。
2. single 和 WF 不再共享同一个结果解释层。
3. packager 退回到“只写 payload”的纯物理职责。
4. Python 结果视图层单独收口，导出入口统一改成纯投影式 `prepare_export(...) -> PreparedExportBundle`。

## 4. 本文件不冻结什么

本文件只解释为什么要这样拆。

正式 contract 见 `../02_spec/05_export_adapter_contracts.md` 和 `../02_spec/06_python_runner_view_and_bundle_contracts.md`，那里才定义：

1. adapter 的职责边界。
2. payload 的最小结构。
3. Python runner view / bundle 的正式对象分层。
4. 正式 Zip 路径。
5. `prepare_export(...)`、bundle 与 `display(...)` 的正式关系。
