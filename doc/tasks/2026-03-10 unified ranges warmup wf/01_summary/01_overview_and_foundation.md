# 核心对象与共享真值

本卷是整套摘要文档的共享定义入口。

这里不展开具体业务流程，只定义后续 `02~05` 共同依赖的核心对象、共享真值和通用 contract。

本组摘要里的函数签名默认只表达对象来源、阶段顺序与返回主干；失败语义与 fail-fast 分支统一由正文、伪代码和 contract 表定义，不要求在伪签名里展开最终 Rust 返回类型。

## 对象归属与边界

本卷定义：

1. `WarmupRequirements`
2. `TimeProjectionIndex`
3. `DataPack / ResultPack / SourceRange`
4. `RawIndicators / TimedIndicators`

本卷消费：

1. 指标参数与 backtest 参数的共享 helper 输入
2. builder、mapping 与时间投影所需的原始容器字段

本卷不负责：

1. 取数状态机
2. 单次回测执行流程
3. WF 窗口规划与 stitched 组装
4. replay kernel

本卷同时承接跨章节的错误体系约束：

1. 本任务涉及的新错误与失败分支，必须优先复用项目现有的 Rust 错误体系，不新增平行错误系统。
2. 总入口优先使用 `QuantError`；能落到已有子错误类型时，优先复用已有 `BacktestError / IndicatorError / SignalError / OptimizerError`。
3. 只有在现有错误枚举无法表达时，才允许在原有错误体系内部补分支；Python / PyO3 暴露层也直接承接这套 Rust 错误映射。

## 分卷地图

### [01_overview_and_foundation_1_shared_resolvers_and_warmup.md](./01_overview_and_foundation_1_shared_resolvers_and_warmup.md)

负责 `WarmupRequirements`：

1. shared resolver / helper
2. `W_resolved / W_normalized / W_applied / W_backtest_exec_base / W_required`
3. 指标 warmup 与 backtest exec warmup 的汇合口径

### [01_overview_and_foundation_2_types_and_mapping.md](./01_overview_and_foundation_2_types_and_mapping.md)

负责 `TimeProjectionIndex` 与容器 contract：

1. `DataPack / ResultPack / SourceRange`
2. `mapping.time` 与 `ranges` 不变式
3. 时间投影工具函数
4. coverage 校验与 mapping builder
5. `RawIndicators / TimedIndicators` 的状态边界

这里的 `TimeProjectionIndex` 不是标签式新名字，而是这一组共享真值的统一归属：

1. `exact_index_by_time(...)`
2. `map_source_row_by_time(...)`
3. `map_source_end_by_base_end(...)`
4. `validate_coverage(...)`
5. `build_mapping_frame(...)`
6. `mapping` 列集合 / dtype / non-null contract

后续 `02~04` 里凡是涉及时间投影、coverage、mapping builder 或容器时间轴复用，都必须先回到这一组定义；不允许在流程文档里再拼第二套时间投影解释链。

## 使用方式

1. 涉及 warmup 真值链，回到分卷一。
2. 涉及容器结构、时间投影、mapping 或 builder 约束，回到分卷二。
3. 后续 `02~05` 只写各自如何消费这些对象与 contract，不复制本卷定义。
