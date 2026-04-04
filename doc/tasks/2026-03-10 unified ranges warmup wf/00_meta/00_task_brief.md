# 03-10 任务简述

本任务是一次高耦合的统一化重构，主题是：

1. 统一 `ranges / warmup / walk forward / stitched` 的真值链。
2. 收口输入输出容器、共享 mapping、单次回测产物与 WF 运行边界。
3. 清理旧桥接、旧兼容与旧公开壳层，按 breaking change 完成收口。

本目录中的核心设计与执行内容，原先是在较早的两层结构 `01_summary / 02_execution` 下编写的。当前目录仅做结构重组，以对齐最新 `AGENTS.md` 的 task spec 组织方式，不改写 `03-10` 原有逻辑结论。

阅读入口：

1. [task_summary.md](./task_summary.md)
2. [../01_context/01_problem_context.md](../01_context/01_problem_context.md)
3. [../02_spec/01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
4. [../03_execution/01_execution_plan.md](../03_execution/01_execution_plan.md)
