# 统一 Ranges / Warmup / WF 执行前 AI 审阅报告

对应文档：

1. [01_execution_plan.md](./01_execution_plan.md)
2. [02_test_plan.md](./02_test_plan.md)
3. [06_test_plan_supplementary.md](./06_test_plan_supplementary.md)
4. [03_execution_stages_and_acceptance.md](./03_execution_stages_and_acceptance.md)
5. [../00_meta/task_summary.md](../00_meta/task_summary.md)
6. [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
7. [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)

本页只记录执行前 AI 审阅结论；执行后补充审阅见 [../04_review/01_post_execution_review.md](../04_review/01_post_execution_review.md)。

## 1. 本次执行前审阅

审阅范围：

1. `02_spec/*`
2. `03_execution/01_execution_plan.md`
3. `03_execution/02_test_plan.md`
4. `03_execution/06_test_plan_supplementary.md`
5. `03_execution/03_execution_stages_and_acceptance.md`

审阅结论：

1. 当前任务包已具备进入代码落地的文档条件。
2. 摘要层已写死：
   - `WarmupRequirements`
   - `TimeProjectionIndex`
   - `RunArtifact`
   - `WalkForwardPlan`
   - `StitchedReplayInput`
   - `ResolvedRegimePlan`
   的对象归属与关键 contract。
3. 执行层已写死：
   - 分阶段迁移口径
   - 旧公开 API 与新核心类型的桥接策略
   - 阶段 D1 / D2 / E 的 stitched 边界
   - 模块拆分约束
   - Rust 负责 kernel 等价性主基线
   - Python 负责 PyO3 / stub 与公开黑盒 gate
   - A2 已把 `strip_indicator_time_columns(...)` 提升为 dedicated contract gate
   - 阶段 gate 与最小测试
4. 当前剩余风险不属于“文档未闭环”，而属于后续实现是否严格按文档落地。

本次审阅重点确认：

1. 共享 warmup helper 链只有一套口径。
2. 时间投影 / coverage 只有一套 fail-fast 口径。
3. `04` 负责 stitched orchestration，`05` 负责 segmented replay 算法与 contract。
4. stitched 正式真值只走 segmented replay，不走资金列重建路径。
5. 阶段 A1 / A2 不切 WF 公共返回；阶段 E 一次性完成公共返回切换。
6. 阶段 D 已拆成 D1 / D2，窗口几何与 stitched 上游输入分开验收。

执行前 gate 结论：

1. 在当前修正后的阶段拆分与桥接策略前提下，可进入阶段 A1。
