# 统一 Ranges / Warmup / WF 重构摘要阅读入口

本目录承载这次 `unified ranges / warmup / walk forward / stitched` 重构的摘要文档。

这组文档只做一件事：把高耦合链路里的真值、计划、运行输入、消费边界一次性钉死，避免后续实现 quietly wrong。

## 阅读顺序

按“共享真值 -> 取数状态机 -> 单次运行产物 -> WF / stitched -> segmented replay”的顺序读：

1. [01_overview_and_foundation.md](./01_overview_and_foundation.md)
2. [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)
3. [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)
4. [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)
5. [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md)

## 按问题检索

若不是顺读，而是针对某个局部 contract 回跳核对，按下面的入口最快：

1. warmup 真值链、shared helper、`W_required` 与容器真实 `warmup_bars` 的层次关系：
   - 看 [01_overview_and_foundation.md](./01_overview_and_foundation.md)
2. `mapping`、coverage、时间投影、`DataPack / ResultPack` 容器 contract：
   - 看 [01_overview_and_foundation.md](./01_overview_and_foundation.md)
3. Python / Rust 职责、初始取数状态机、首尾补拉、初始 `ranges`：
   - 看 [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)
   - 取数算法、初始 `ranges` 与 `finish()` 细节见 [02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](./02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md)
4. 单次回测主流程、`build_result_pack(...)`、`extract_active(...)`、同源配对边界：
   - 看 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)
5. WF 窗口公式、跨窗注入、窗口返回、`NextWindowHint`、stitched 上游输入：
   - 看 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)
6. segmented replay、schedule、kernel、schema、等价性与测试基线：
   - 看 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md)

## 核心真值链速览

对 quietly wrong 风险最高的链路，入口页保留精简真值表，不只保留抽象对象名。

| 层级 | 正式名称 | 含义 | 主要消费方 |
| --- | --- | --- | --- |
| 指标契约原始聚合 | `W_resolved[k]` | `resolve_indicator_contracts(...)` 返回的 source 级原始 warmup 聚合结果 | `01` |
| 补全到当前 source 全集 | `W_normalized[k]` | 把 `W_resolved[k]` 补全到当前 `S_keys`；缺失 key 统一补 `0` | `01` |
| WF 指标策略作用后 | `W_applied[k]` | 在 `W_normalized[k]` 上应用 `ignore_indicator_warmup` 后的指标 warmup | `01`、`04` |
| base 轴回测执行预热 | `W_backtest_exec_base` | base 轴 backtest exec warmup | `01`、`02`、`04` |
| 合并回测执行预热后 | `W_required[k]` | 把 `W_applied[k]` 与 `W_backtest_exec_base` 合并后的最终 required warmup | `02`、`04` |
| 当前容器真实前导边界 | `data.ranges[k].warmup_bars` | 当前切片结果最终落地到容器里的真实预热长度 | `03`、`04`、`05` |

## 对象归属总表

本组文档采用“对象归属优先，阶段消费次之”的组织方式。稳定真值按对象写，强流程逻辑按阶段写。

| 对象 | 类别 | 边界层级 | 总定义文档 / 阶段强化文档 | 生产阶段 | 主要消费阶段 |
| --- | --- | --- | --- | --- | --- |
| `WarmupRequirements` | 共享真值对象 | 概念对象 | `01` | shared resolvers / WF precheck | `02`、`04`、`05`、回测入口 |
| `TimeProjectionIndex` | 共享真值对象 | 概念对象 | `01` | initial build / slicing | `02`、`03`、`04` |
| `DataPack` | 容器真值对象 | 正式 Rust-PyO3 边界对象 | `01` | initial build / slicing | 全流程 |
| `ResultPack` | 容器真值对象 | 正式 Rust-PyO3 边界对象 | `01` 总定义；`03` 阶段强化 | single run / stitched build | `03`、`04`、导出 |
| `RawIndicators / TimedIndicators` | 结果状态对象 | 概念对象 | `01` 总定义；`03` 流转与 builder 强化 | indicator stage / result build | `03`、`04`、最终 stitched 构建 |
| `DataPackFetchPlanner / SourceFetchState` | 计划对象 | 内部计划对象 | `02` | Python fetch planning | fetch loop |
| `RunArtifact` | 运行配对对象 | 概念对象 | `03` | single run | `extract_active(...)`、WF 测试侧同源 `DataPack / ResultPack` 路径、导出、调试 |
| `WalkForwardConfig` | 公共输入对象 | 正式 Rust-PyO3 边界对象 | `04` | WF 入口配置 | `run_walk_forward(...)` |
| `WalkForwardPlan` | 计划对象 | 内部计划对象 | `04` | WF precompute | window runner |
| `WindowIndices / WindowSliceIndices` | 窗口切片计划对象 | 内部计划对象 | `04` | `WalkForwardPlan` 内部 | per-window pack materialization |
| `WindowArtifact / StitchedArtifact / NextWindowHint` | 返回对象 | 正式 Rust-PyO3 边界对象 | `04` | per-window execution / stitched assembly | Python 展示 / 调度提示 / 总结果导出 |
| `WalkForwardResult` | 公共返回对象 | 正式 Rust-PyO3 边界对象 | `04` | WF 总流程尾部 | Python 消费与导出 |
| `StitchedReplayInput` | 运行输入对象 | 内部运行输入对象 | `04` | stitched materialization | `05` replay 与最终 stitched 构建 |
| `ResolvedRegimePlan` | 计划对象 | 概念对象 | `05` | schedule validation / selector construction | replay kernel |

补充边界：

1. 边界层级解释：
   - 概念对象：用于收纳既有真值链与 contract 归属，不要求等于单一 Rust 公共结构体。
   - 内部计划对象 / 内部运行输入对象：摘要里的阶段对象，用于组织执行边界，不要求直接成为公共 PyO3 类型。
   - 正式 Rust-PyO3 边界对象：必须落到 Rust 类型定义、PyO3 暴露与 stub 生成链上。
2. `WindowSliceIndices` 是窗口切片计划对象的正式名字；它在 `04` 中承担窗口切片计划对象角色，不单独再引入第二套平行命名。
3. `StitchedReplayInput` 是 `04 -> 05` 的正式运行输入对象名字；它不是顶层公共 PyO3 输入对象。
4. 表中的“总定义文档 / 阶段强化文档”表示：
   - 总定义文档负责对象通用形状与基础 contract
   - 阶段强化文档只负责在具体流程里施加更强阶段约束
   - 同一事实仍然只保留一个归属，不允许两边各自改真值
5. `ResultPack.performance` 保持通用指标字典形态：`Option<HashMap<String, f64>>`；键集由 `PerformanceParams.metrics` 与 `PerformanceMetric` 决定。

## 阶段消费总图

```text
01 共享真值层
    -> 定义 WarmupRequirements / TimeProjectionIndex / DataPack / ResultPack

02 取数状态机
    -> 消费 01 的共享真值
    -> 产出 DataPack

03 单次运行
    -> 消费 DataPack
    -> 产出 ResultPack
    -> 以 RunArtifact 视角绑定同源 DataPack + ResultPack

04 WF / stitched
    -> 消费 DataPack / WalkForwardConfig
    -> 产出 WalkForwardPlan / WindowArtifact / StitchedArtifact / NextWindowHint / StitchedReplayInput / WalkForwardResult

05 segmented replay
    -> 消费 StitchedReplayInput
    -> 在 ResolvedRegimePlan 约束下执行 replay kernel
    -> 产出正式 stitched backtest 真值
```

## 全局原则

1. 全文统一使用半开区间 `[start, end)`；索引默认都是相对于当前容器自身 DataFrame 的局部行号。
2. 真正参与切片、重基、拼接的边界，只认当前容器里的 `ranges[k].warmup_bars`；不能直接拿契约 warmup 裁数据。
3. 对象只收纳现有真值与现有 contract，不新增第二套解释路径。
4. 同一事实只保留一个对象归属；执行器只消费对象，不反向拥有领域语义。
5. 本任务按破坏性更新处理，不保留兼容层、旧字段、旧名残留或平行口径。
6. Rust 类型、错误与核心 contract 是单一事实源；Python / PyO3 暴露直接承接这套定义。
7. 摘要里的函数签名默认只表达对象来源、阶段顺序与返回主干；fail-fast 是否存在以及失败如何改变控制流，以正文、伪代码和 contract 表为准，不强制在伪签名里显式写成 `Result<...>`。

## 错误体系约束

1. 本任务涉及的新错误与失败分支，必须优先复用项目现有的 Rust 错误体系，不新增平行错误系统。
2. 总入口优先使用 `QuantError`；能落到已有子错误类型时，优先复用已有 `BacktestError / IndicatorError / SignalError / OptimizerError`。
3. 只有在现有错误枚举无法表达时，才允许在原有错误体系内部补分支；Python / PyO3 暴露层也直接承接这套 Rust 错误映射。

## 各卷定位

### [01_overview_and_foundation.md](./01_overview_and_foundation.md)

负责核心对象与共享真值：

1. `WarmupRequirements`
2. `TimeProjectionIndex`
3. `DataPack / ResultPack / SourceRange`
4. `RawIndicators / TimedIndicators`

### [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)

负责取数状态机与 `DataPack` 构建：

1. `DataPackFetchPlanner`
2. `SourceFetchState`
3. `next_request() / ingest_response() / finish()`
4. 取数算法、初始 `ranges` 与 `finish()` 细节见 [02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](./02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md)

### [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)

负责单次运行产物与配对关系：

1. `ResultPack`
2. `RunArtifact`
3. `build_result_pack(...)`
4. `extract_active(...)`

### [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)

负责窗口规划、窗口执行与 stitched 上游输入：

1. `WalkForwardConfig`
2. `WalkForwardPlan`
3. `WindowIndices / WindowSliceIndices`
4. `WindowArtifact / StitchedArtifact`
5. `StitchedReplayInput`
6. `NextWindowHint / WalkForwardResult`

### [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md)

负责 replay 计划对象与执行边界：

1. `ResolvedRegimePlan`
2. `BacktestParamSegment / ParamsSelector`
3. `run_backtest_with_schedule(...)`
4. kernel、schema、policy、测试基线

## 执行文档入口

1. [../02_execution/01_execution_plan.md](../02_execution/01_execution_plan.md)
2. [../02_execution/02_test_plan.md](../02_execution/02_test_plan.md)
3. [../02_execution/06_test_plan_supplementary.md](../02_execution/06_test_plan_supplementary.md)
