# 向前测试、窗口切片、跨窗注入与 stitched

> 本文件已拆分为目录页；原有 WF / stitched 口径不变。

本篇仍然是 WF / stitched 的 owned 文档入口。阅读顺序：

1. [04_walk_forward_and_stitched_1_windowing_and_injection.md](./04_walk_forward_and_stitched_1_windowing_and_injection.md)
   - 对应原文 `## 1`、`## 2`、`## 4`、`## 5`
   - 包含：
     - 输入与模式
     - `build_window_indices(...)`
     - `slice_data_pack_by_base_window(...)`
     - 跨窗信号注入

2. [04_walk_forward_and_stitched_2_window_execution_and_return.md](./04_walk_forward_and_stitched_2_window_execution_and_return.md)
   - 对应原文 `## 6`、`## 7`
   - 包含：
     - 每个窗口的执行流程
     - WF 返回结构

3. [04_walk_forward_and_stitched_3_stitched_algorithm.md](./04_walk_forward_and_stitched_3_stitched_algorithm.md)
   - 对应原文 `## 8`、`## 9`、`## 10`
   - 包含：
     - stitched 总则
     - stitched 上游输入准备与拼接算法
     - 为什么 stitched 不直接拼窗口 `DataPack / backtest`

引用原则：

1. 其他文档继续把本文件视为 WF / stitched 的总入口引用。
2. 若问题落在窗口规划、跨窗注入、窗口主循环，继续按阅读顺序跳到前两卷。
3. 若问题落在 stitched 正式输入准备、stitched indicators、stitched signals、schedule 与 replay 衔接，直接看第三卷。
4. [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md) 继续作为 stitched 正式 backtest 真值的后续增量文档；`04` 仍然拥有 stitched 上游算法。

拆分说明：

1. 本次拆分只调整排版与阅读路径，不修改 WF / stitched 口径。
2. 分卷文件中的章节编号继续沿用原文编号，方便与既有讨论记录对照。
3. 若后续人工通过 `git diff` 检查是否丢失逻辑，应以分卷正文是否完整承接原章节为准。
