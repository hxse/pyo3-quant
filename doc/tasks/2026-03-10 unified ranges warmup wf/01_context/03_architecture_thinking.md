# 架构分层与阅读顺序

`03-10` 任务原始摘要本身已经按主链分卷组织。当前目录重组后，建议按以下顺序阅读：

1. 共享基础与对象真值：
   [../02_spec/01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
2. Python 取数与初始构建：
   [../02_spec/02_python_fetch_and_initial_build.md](../02_spec/02_python_fetch_and_initial_build.md)
3. 单次回测与结果容器：
   [../02_spec/03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)
4. WF / stitched 结构与算法：
   [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
5. segmented replay 与 kernel：
   [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)

执行文档则按另一条顺序阅读：

1. [../03_execution/01_execution_plan.md](../03_execution/01_execution_plan.md)
2. [../03_execution/02_test_plan.md](../03_execution/02_test_plan.md)
3. [../03_execution/03_execution_stages_and_acceptance.md](../03_execution/03_execution_stages_and_acceptance.md)
4. [../03_execution/07_full_breaking_cleanup_plan.md](../03_execution/07_full_breaking_cleanup_plan.md)

说明：

1. 本页只负责结构导航，不新增新的设计结论。
2. `03-10` 原始内容已经较细，因此这里不再把原文拆写成第二套摘要。
