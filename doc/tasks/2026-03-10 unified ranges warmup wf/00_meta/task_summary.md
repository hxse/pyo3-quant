# 统一 Ranges / Warmup / WF 重构摘要阅读入口

本目录承载这次 `unified ranges / warmup / walk forward / stitched` 重构的摘要文档。

本页只承担阅读入口与检索导航职责；正式真值、对象 contract、全局原则与算法细节统一以 `02_spec` 正文为准。

## 阅读顺序

按“共享真值 -> 取数状态机 -> 单次运行产物 -> WF / stitched -> segmented replay”的顺序读：

1. [01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
2. [02_python_fetch_and_initial_build.md](../02_spec/02_python_fetch_and_initial_build.md)
3. [03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)
4. [04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
5. [05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)

## 按问题检索

若不是顺读，而是针对某个局部 contract 回跳核对，按下面的入口最快：

1. warmup 真值链、shared helper、`W_required` 与容器真实 `warmup_bars` 的层次关系：
   - 看 [01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
2. `mapping`、coverage、时间投影、`DataPack / ResultPack` 容器 contract：
   - 看 [01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
3. Python / Rust 职责、初始取数状态机、首尾补拉、初始 `ranges`：
   - 看 [02_python_fetch_and_initial_build.md](../02_spec/02_python_fetch_and_initial_build.md)
   - 取数算法、初始 `ranges` 与 `finish()` 细节见 [02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](../02_spec/02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md)
4. 单次回测主流程、`build_result_pack(...)`、`extract_active(...)`、同源配对边界：
   - 看 [03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)
5. WF 窗口公式、跨窗注入、窗口返回、`NextWindowHint`、stitched 上游输入：
   - 看 [04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
6. segmented replay、schedule、kernel、schema、等价性与测试基线：
   - 看 [05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)

## 各卷定位

### [01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)

负责核心对象与共享真值：

1. `WarmupRequirements`
2. `TimeProjectionIndex`
3. `DataPack / ResultPack / SourceRange`
4. `RawIndicators / TimedIndicators`

### [02_python_fetch_and_initial_build.md](../02_spec/02_python_fetch_and_initial_build.md)

负责取数状态机与 `DataPack` 构建：

1. `DataPackFetchPlanner`
2. `SourceFetchState`
3. `next_request() / ingest_response() / finish()`
4. 取数算法、初始 `ranges` 与 `finish()` 细节见 [02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](../02_spec/02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md)

### [03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)

负责单次运行产物与配对关系：

1. `ResultPack`
2. `RunArtifact`
3. `build_result_pack(...)`
4. `extract_active(...)`

### [04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)

负责窗口规划、窗口执行与 stitched 上游输入：

1. `WalkForwardConfig`
2. `WalkForwardPlan`
3. `WindowIndices / WindowSliceIndices`
4. `WindowArtifact / StitchedArtifact`
5. `StitchedReplayInput`
6. `NextWindowHint / WalkForwardResult`

### [05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)

负责 replay 计划对象与执行边界：

1. `ResolvedRegimePlan`
2. `BacktestParamSegment / ParamsSelector`
3. `run_backtest_with_schedule(...)`
4. kernel、schema、policy、测试基线

## 执行文档入口

1. [../03_execution/01_execution_plan.md](../03_execution/01_execution_plan.md)
2. [../03_execution/02_test_plan.md](../03_execution/02_test_plan.md)
3. [../03_execution/06_test_plan_supplementary.md](../03_execution/06_test_plan_supplementary.md)
