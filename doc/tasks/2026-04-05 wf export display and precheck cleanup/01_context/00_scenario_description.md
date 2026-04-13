# 场景描述

## 1. 这次任务收的是执行层外围，不是 `03-10` 主算法

`03-10` 已经把 warmup / window / stitched 主算法落到了 Rust 主链。

`04-05` 当前真正要收的，不是主算法本身，而是围绕它长出来的几层外围解释层：

1. Python precheck 与正式入口之间的双轨语义。
2. WF 局部 replay 与 single 正式执行之间的分叉控制流。
3. `execution_stage` / `return_only_final` 在公开层与内部层混用造成的语义缠绕。
4. `ResultPack` 既当公开结果，又被拿去当内部中间货币的边界污染。
5. `DataPack` / `ResultPack` 作为公开类型存在，但又仍允许直接手造对象，导致真值落点漂移。
6. `py_entry/runner` 的 Python wrapper 层把结果视图、导出会话、display/save/upload、副本缓存和临时兼容代理揉在一起。

这里要先澄清一个容易误读的点：

这次任务不是“全部只重构结构、全部逻辑完全等价”。

更准确的分层是：

1. `03-10` 已冻结的 warmup / window / stitched 主算法不改，相关执行行为必须保持等价。
2. single / batch 的公开 `stop_stage × artifact_retention` 语义，以及 WF / optimizer / sensitivity 的既有模式语义，要求等价迁移。
3. Python runner wrapper 模块的对象分层、导出入口和 display 边界允许做破坏性收口，但不得改变各模式底层计算语义。
4. Python precheck 删除、pack producer 收口、source time 严格递增 contract、Renko 退出正式入口，这些都是有意的 contract 收紧，不属于纯结构重排。

## 2. 当前真正缠在一起的不是一个类名，而是 4 件不同的事

当前代码把下面 4 件事揉在了一起：

1. 公开调用希望停在哪一层。
2. 内部局部 replay 希望从哪一层继续。
3. 已完成阶段的产物要保留多少。
4. 哪些对象属于公开边界，哪些对象只属于内部执行。

`BacktestContext` 之所以看起来混乱，只是因为这 4 件事没有被分开表达。

## 3. 为什么 `BacktestContext` 会越长越歪

当前执行层里有三个明显的结构性空洞：

1. single / batch 的 Rust 正式入口在命名、物理归属和对外语义上仍不够对称。
2. 内部执行器没有“从 `Signals` 起跑”的第一类请求模型。
3. optimizer / sensitivity / WF 都直接碰内部 single 执行能力，但各自又长出了不同命名和不同边界。

在这种前提下，WF 想做 natural replay / final replay，只能靠一个 mutable context 去同时承担：

1. 暂存阶段产物。
2. 继续 backtest / performance。
3. 再把结果回装成 `ResultPack`。

所以病根不是 `BacktestContext` 这个名字，而是执行层缺了正式抽象。

## 4. 这次选择的设计方向

这次任务在执行层上收口到下面 5 条：

1. 公开设置只表达公开 stop 语义和公开产物保留语义。
2. 内部 replay 起点另起一个维度，不再借公开设置偷传。
3. `ResultPack` 只在公开边界和公开 artifact 边界构建，不再作为内部评估货币。
4. 内部执行的输入与输出都收成严格类型，一一对应，不再依赖 `Option` 袋子表达阶段 shape。
5. 顶层入口、内部执行、样本评估、WF replay 使用不同动词体系。

这次任务在 Python wrapper 层也收口到下面 4 条：

1. `Backtest` 保留为执行门面，不再让结果对象承担门面职责。
2. Python 结果层收口为统一的 view 体系，不再混用 `Result / Wrapper / OptResult` 几套命名。
3. 导出会话与结果视图分离，display/save/upload 只消费 bundle。
4. WF stitched 不再通过伪造 single `RunResult` 视图复用导出链路。

具体说，就是：

1. `SettingContainer` 只负责 `stop_stage` 与 `artifact_retention`，并保持与现有 `execution_stage / return_only_final` 组合语义等价。
2. 内部执行不再用松散的起点枚举配合若干 `Option` 输入，而是直接使用严格的 `PipelineRequest` 表达合法请求。
3. 内部执行器直接返回严格的 `PipelineOutput`，不再返回带 `Option` 的中间结果袋。
4. `build_result_pack(...)` 只负责把 `PipelineOutput` 整理成公开结果。
5. `DataPack` / `ResultPack` 只允许通过 producer 真值入口产出，不再依赖执行入口额外兜底。
6. Python 结果视图层收口为 `SingleBacktestView / BatchBacktestView / WalkForwardView / OptimizationView / SensitivityView / OptunaOptimizationView`。
7. 导出会话层收口为 `PreparedExportBundle`，由 view 纯投影生成，不再在 view 上缓存导出副作用状态。

## 5. 这次设计最关键的取舍

### 5.1 `BacktestContext` 不改名，直接删除

更优雅的方向不是把它改成 `ExecutionArtifacts` 或别的名字，而是把真正缺的“执行请求 / replay 起点 / 内部阶段产物”补成正式执行层能力。

### 5.2 `execution_stage` 的职责收窄成公开 stop 语义

它仍然有价值，因为 single / batch 真实需要部分执行。

但它不再承担“内部从哪起跑”的职责。内部 replay / single 请求由严格的 `PipelineRequest` 单独表达。

### 5.3 `return_only_final` 不再保留为布尔语义

布尔值把“公开产物保留”与“内部释放上游中间结果”混在了一起，语义过于隐晦。

更清晰的方向是公开层显式使用 `artifact_retention`，内部据此推导是否释放已消费的上游阶段产物。

### 5.4 optimizer / sensitivity / WF 的模式边界要写死

这三个模式的公开结果都不是“任意 stop_stage 的单次结果”。

因此它们不能再模糊地复用 single 的设置语义，而是要明确：

1. WF 公开模式是 performance 级结果模式。
2. optimizer 是 performance 采样评估模式。
3. sensitivity 是 performance 抖动评估模式。

## 6. 这轮 context 要达成的结论

1. `BacktestContext` 退出正式设计。
2. 正式对象分层改成：Rust 业务入口 `run_*`、PyO3 wrapper `py_run_*`、内部执行器 `execute_*`、样本评估 `evaluate_*`。
3. 公开设置与内部 replay 起点分离。
4. `ResultPack` 回到公开边界对象的位置。
5. `DataPack` / `ResultPack` 收口为 formal contract object，只允许由 producer 真值入口产出。
6. 内部执行核心真值收口为 `PipelineRequest -> PipelineOutput`。
7. Python wrapper 模块正式收口为“门面 + session + views + export bundle”四层，不再长期保留 `RunResult` / `WalkForwardResultWrapper` 这类过渡壳。
