# 问题背景

`03-10 unified ranges warmup wf` 的问题背景是：旧链路里存在多处历史残留，导致同一组运行真值在不同对象、不同阶段与不同语言侧被重复表达，容易产生 quietly wrong 风险。

本任务要解决的不是单点 bug，而是一整条高耦合链路的统一化问题，重点包括：

1. `ranges / warmup / mapping` 的共享真值。
2. Python 取数与 Rust 构建的正式边界。
3. 单次回测产物与 active 区间的唯一口径。
4. `walk forward / stitched / segmented replay` 的结构性 contract。
5. 旧桥接、旧兼容与旧公开壳层的最终收口。

本页只解释“为什么这次任务需要成立”，正式对象定义与算法真值统一在 `02_spec`。

对应阅读：

1. [../02_spec/01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
2. [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
3. [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)
