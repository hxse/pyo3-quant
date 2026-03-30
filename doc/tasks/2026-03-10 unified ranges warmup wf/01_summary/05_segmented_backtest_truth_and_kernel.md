# 分段真值回测、可变 ATR 与对现有主循环的精准抽象

> 本文件已拆分为目录页；原有 segmented replay 口径不变。

本篇仍然是对 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 的后续增量方案讨论，只专门负责：

1. segmented replay 的目标口径
2. `run_backtest_with_schedule(...)`
3. 通用 kernel
4. output schema / stitched 输入 / 测试策略

阅读顺序：

1. [05_segmented_backtest_truth_and_kernel_1_design_and_selector.md](./05_segmented_backtest_truth_and_kernel_1_design_and_selector.md)
   - 对应原文 `## 0` 至 `## 7`
   - 包含：
     - 归属与边界
     - 总体方案
     - 边界问题
     - `atr_period`
     - 统一参数选择器

2. [05_segmented_backtest_truth_and_kernel_2_kernel_and_entries.md](./05_segmented_backtest_truth_and_kernel_2_kernel_and_entries.md)
   - 对应原文 `## 8`、`## 9`
   - 包含：
     - 通用 kernel
     - 两个入口与调用链

3. [05_segmented_backtest_truth_and_kernel_3_schema_outputs_and_tests.md](./05_segmented_backtest_truth_and_kernel_3_schema_outputs_and_tests.md)
   - 对应原文 `## 10` 至 `## 14`
   - 包含：
     - output schema
     - stitched 阶段产物
     - 影响范围
     - 等价性测试
     - 非目标与最终结论

引用原则：

1. 其他文档继续把本文件视为 segmented replay 的总入口引用。
2. 若问题落在设计判断、边界语义、参数选择器，先看第一卷。
3. 若问题落在 kernel 与入口等价性，先看第二卷。
4. 若问题落在 schema、stitched 输入、测试与 review 约束，先看第三卷。

拆分说明：

1. 本次拆分只调整排版与阅读路径，不新增第二套 replay 口径。
2. 分卷文件中的章节编号继续沿用原文编号，方便与既有讨论记录对照。
3. 若后续人工通过 `git diff` 检查是否丢失逻辑，应以分卷正文是否完整承接原章节为准。
