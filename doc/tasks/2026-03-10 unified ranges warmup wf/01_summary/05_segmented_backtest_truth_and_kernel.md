# 分段真值回测、可变 ATR 与对现有主循环的精准抽象

本卷是 stitched 正式 backtest 真值的增量方案入口。

它建立在 `04` 已经准备好的 stitched 上游输入之上，只新增 segmented replay、schedule backtest 与通用 kernel 这一层语义。

## 本卷作用

1. 定义正式 stitched backtest 真值如何由 `run_backtest_with_schedule(...)` 生成。
2. 定义 `BacktestParamSegment`、`ParamsSelector` 与通用 kernel。
3. 定义 schedule 路径下的 schema、policy、测试与等价性审阅重点。

## 分卷地图

### [05_segmented_backtest_truth_and_kernel_1_design_and_selector.md](./05_segmented_backtest_truth_and_kernel_1_design_and_selector.md)

负责：

1. stitched replay 的目标口径
2. 什么变、什么不变
3. `atr_period` 可变的边界
4. `BacktestParamSegment` 与 `ParamsSelector`

### [05_segmented_backtest_truth_and_kernel_2_kernel_and_entries.md](./05_segmented_backtest_truth_and_kernel_2_kernel_and_entries.md)

负责：

1. 通用 kernel
2. `run_backtest(...)` 与 `run_backtest_with_schedule(...)` 的收敛关系
3. schedule 验证链与等价性审阅重点

### [05_segmented_backtest_truth_and_kernel_3_schema_outputs_and_tests.md](./05_segmented_backtest_truth_and_kernel_3_schema_outputs_and_tests.md)

负责：

1. output schema
2. stitched replay 的正式产物
3. 对现有 `03-10` 方案的影响范围
4. Rust 侧测试基线与非目标

## 和 `04` 的边界

1. `04` 负责窗口级真值和 stitched 上游输入准备。
2. `05` 负责连续 replay、schedule 参数选择和最终 stitched backtest 真值。
3. stitched 的正式 backtest 真值由 `05` 的 segmented replay 生成。

## 阅读提醒

1. 本卷不改 planner，不改 `01` 的 warmup 三层口径，不改 `04` 的窗口级信号语义。
2. 本卷只接管“如何把 `04` 产出的 stitched 输入交给回测引擎，再得到正式 stitched backtest”这一层。
