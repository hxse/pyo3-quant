# 统一 Ranges / Warmup / WF 重构总述与基础约束

> 本文件已拆分为目录页；原有方案口径不变。

本篇仍然是 `01-04` 的共享定义入口。阅读顺序：

1. [01_overview_and_foundation_1_shared_resolvers_and_warmup.md](./01_overview_and_foundation_1_shared_resolvers_and_warmup.md)
   - 对应原文 `## 0`、`## 1`、`## 2`
   - 包含：
     - 文档归属与引用规则
     - shared resolver / helper
     - `W_resolved / W_normalized / W_applied / W_required`
     - 指标预热与 backtest exec warmup

2. [01_overview_and_foundation_2_types_and_mapping.md](./01_overview_and_foundation_2_types_and_mapping.md)
   - 对应原文 `## 3`、`## 4`
   - 包含：
     - `DataPack / ResultPack / SourceRange`
     - `build_data_pack(...) / build_result_pack(...)`
     - `build_mapping_frame(...)`
     - mapping 与覆盖校验

阅读原则：

1. 任何关于 warmup 三层、shared helper、`W_required` 的问题，先看分卷一。
2. 任何关于核心容器、builder、mapping 真值的问题，先看分卷二。
3. [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)、[03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)、[04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 继续把本文件当作共享入口引用即可；需要细节时再跳到对应分卷。

拆分说明：

1. 本次拆分只调整排版与阅读路径，不新增第二套定义。
2. 分卷文件中的章节编号继续沿用原文编号，方便与既有讨论记录对照。
3. 若后续人工通过 `git diff` 检查是否丢失逻辑，应以分卷正文是否完整承接原章节为准。
