# 分段真值回测、可变 ATR 与对现有主循环的精准抽象

本卷是 stitched 正式 backtest 真值的摘要入口。

它建立在 `04` 已经准备好的 stitched 上游运行输入之上，只定义 replay 计划对象、schedule contract 与通用 kernel 的消费边界。

## 对象归属与边界

本卷定义：

1. `ResolvedRegimePlan`
2. `BacktestParamSegment / ParamsSelector`
3. `run_backtest_with_schedule(...)`

本卷消费：

1. `StitchedReplayInput`
2. `WarmupRequirements` 的既有结论
3. `04` 已经稳定的窗口信号与 stitched 输入语义

本卷不负责：

1. planner 状态机
2. 窗口规划
3. stitched 指标拼接
4. 回测前的输入物化算法

本卷保持“对象 contract + 执行器边界”的写法：先定义计划对象和输入 contract，再定义 kernel 如何消费它们。

## 分卷地图

### [05_segmented_backtest_truth_and_kernel_1_design_and_selector.md](./05_segmented_backtest_truth_and_kernel_1_design_and_selector.md)

负责：

1. `ResolvedRegimePlan`
2. `BacktestParamSegment` 与 `ParamsSelector`
3. `StitchedReplayInput` 的消费边界
4. stitched replay 的目标口径

### [05_segmented_backtest_truth_and_kernel_2_kernel_and_entries.md](./05_segmented_backtest_truth_and_kernel_2_kernel_and_entries.md)

负责：

1. 通用 kernel
2. `run_backtest(...)` 与 `run_backtest_with_schedule(...)` 的收敛关系
3. `ResolvedRegimePlan` 的验证链与等价性审阅重点

### [05_segmented_backtest_truth_and_kernel_3_schema_outputs_and_tests.md](./05_segmented_backtest_truth_and_kernel_3_schema_outputs_and_tests.md)

负责：

1. output schema
2. stitched replay 的正式产物
3. Rust 侧测试基线与非目标

## 阅读提醒

1. 本卷不改 planner，不改 `01` 的 warmup 三层口径，不改 `04` 的窗口级信号语义。
2. `05` 只接管“如何在 `ResolvedRegimePlan` 约束下消费 `StitchedReplayInput`，再得到正式 stitched backtest”这一层。
