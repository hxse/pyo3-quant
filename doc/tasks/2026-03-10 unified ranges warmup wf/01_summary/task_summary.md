# 统一 Ranges / Warmup / WF 重构摘要阅读入口

本目录承载这次 `unified ranges / warmup / walk forward / stitched` 重构的摘要文档。

这组文档的目标只有一个：把高耦合链路里的真值、对象来源、索引空间、失败语义一次性钉死，避免后续实现出现 quietly wrong。

## 如何读这组文档

先按“共享定义 -> 取数 -> 单次回测 -> WF / stitched -> segmented replay”的顺序读。

若你只想回答局部问题，不必通读整套文档，但要先确认这个问题属于哪一层：

1. 共享术语、warmup 真值链、容器不变式、mapping / coverage / 时间投影工具函数：
   - 先看 [01_overview_and_foundation.md](./01_overview_and_foundation.md)
2. Python / Rust 职责划分、初始取数状态机、首尾补拉、初始 `ranges`：
   - 看 [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)
3. 单次回测主流程、`build_result_pack(...)`、`extract_active(...)`：
   - 看 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)
4. WF 窗口规划、窗口切片、跨窗注入、stitched 上游输入准备：
   - 看 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)
5. segmented replay、schedule、kernel、schema、测试基线：
   - 看 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md)

## 阅读时先记住的 4 条总原则

1. 这次重构按破坏性更新处理，不保留兼容层，不维护旧名残留。
2. 全文统一使用半开区间 `[start, end)`；索引默认都是“相对于当前容器自身 DataFrame 的局部行号”。
3. 真正参与切片、重基、拼接的边界，只认当前容器里的 `ranges[k].warmup_bars`；不能直接拿契约 warmup 裁数据。
4. Rust 是核心边界类型与错误体系的唯一事实源；Python 不维护镜像核心类型。

## 场景与设计出发点

1. 这次重构的目标是把原本就存在的复杂度收回到框架内部，避免继续外包给调用方。
2. 项目需要同时支持多周期数据、自动预热、统一回测、向前测试、窗口切片与 stitched；这些能力组合起来，问题就从单函数实现变成了时间轴、mapping、ranges 与窗口语义的一致性。
3. 因此本任务追求的是唯一写法、唯一语义、唯一工作流，让用户层与 AI 调用层尽量只做配置和网络请求，不承担高风险真值逻辑。

## 全局硬约束

### 类型边界

1. 只要某个核心输入/输出类型可以直接在 Rust 端定义并通过 PyO3 暴露，就必须以 Rust 为唯一事实源，并通过 `just stub` 自动生成 `.pyi`。
2. 对这类核心边界类型，Python 侧不得再维护同语义的镜像类型、平行 dataclass、平行 Pydantic 模型或手写 `.pyi`。
3. 本任务里的 `DataPack / ResultPack / SourceRange / WalkForwardConfig / WalkForwardResult / WindowArtifact / StitchedArtifact / NextWindowHint` 都属于这条约束覆盖范围。

### 错误系统

1. 本任务涉及的新错误与失败分支，必须优先复用项目现有的 Rust 错误体系，不新增平行错误系统。
2. 优先复用 `src/error` 下已经存在的错误入口与子错误类型，例如 `QuantError / BacktestError / IndicatorError / SignalError / OptimizerError`。
3. 只有在现有错误枚举无法表达时，才允许在原有错误体系内部补分支；Python / PyO3 暴露层也应直接承接这套 Rust 错误映射。

## 核心真值链

这一组文档最容易反复出现的是 warmup 与容器边界。先把真值链压成一张表，后面各卷默认引用这里。

| 层级 | 正式名称 | 含义 | 主要消费方 |
| --- | --- | --- | --- |
| 指标契约原始聚合 | `W_resolved[k]` | `resolve_indicator_contracts(...)` 返回的 source 级原始 warmup 聚合结果；允许不覆盖全部 `S_keys` | `01` |
| 补全到当前 source 全集 | `W_normalized[k]` | 把 `W_resolved[k]` 补全到当前 `S_keys`；缺失 key 统一补 `0` | `01` |
| WF 指标策略作用后 | `W_applied[k]` | 在 `W_normalized[k]` 上应用 `ignore_indicator_warmup` 后的指标 warmup | `01`、`04` |
| 合并回测执行预热后 | `W_required[k]` | 把 `W_applied[k]` 与 base 轴 backtest exec warmup 合并后的最终 required warmup | `02`、`04` |
| 当前窗口或当前容器真实前导边界 | `warmup_by_key[k]` / `ranges[k].warmup_bars` | 当前切片结果实际落地到容器里的真实预热长度 | `03`、`04`、`05` |

## 每一卷真正拥有的内容

### [01_overview_and_foundation.md](./01_overview_and_foundation.md)

1. 共享 warmup resolver / helper
2. `DataPack / ResultPack / SourceRange`
3. `mapping.time`、ranges 不变式
4. 三个统一时间投影工具函数
5. coverage 校验与 mapping builder

### [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)

1. Python 只做网络请求
2. Rust `DataPackFetchPlanner` 状态机
3. base / source 的补尾覆盖、补首时间覆盖、补首预热
4. 初始 `ranges` 的正式计算
5. Rust 内部调用 `build_data_pack(...)`

### [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)

1. 单次回测主流程
2. 绩效只统计 `active 区间` 的正式口径
3. `build_result_pack(...)` 的字段构建规则
4. `extract_active(...)` 的轻量 active view 语义

### [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)

1. `WalkForwardConfig`、参数来源与窗口模式
2. `build_window_indices(...)`
3. `slice_data_pack_by_base_window(...)`
4. 跨窗 carry 注入与尾部强平
5. stitched 上游输入准备

### [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md)

1. 正式 stitched backtest 真值从“窗口 backtest 拼接”切换到“segmented replay”
2. `run_backtest_with_schedule(...)`
3. 通用 kernel 与 `ParamsSelector`
4. output schema、policy、测试与等价性校验

## 这次拆分后的阅读策略

1. 目录页只负责导航。
2. 共享定义只在 `01` 写完整一遍；后续章节只写“本章怎样消费这些定义”。
3. `04` 只负责 WF / stitched 上游与窗口级真值；`05` 只负责 segmented replay 和 schedule backtest 真值。
4. 若要核对是否丢逻辑，应看分卷正文是否完整承接原章节，不看目录页长短。

## 执行文档入口

1. [../02_execution/01_execution_plan.md](../02_execution/01_execution_plan.md)
2. [../02_execution/02_test_plan.md](../02_execution/02_test_plan.md)
