# 向前测试、窗口切片、跨窗注入与 stitched

本卷是 WF / stitched 的摘要入口。

本卷统一引用共享 warmup / mapping / container 定义，正文只写窗口规划对象、窗口执行对象和 stitched 上游运行输入。

## 对象归属与边界

本卷定义：

1. `WalkForwardConfig`
2. `WalkForwardPlan`
3. `WindowIndices / WindowSliceIndices`
4. `WindowArtifact / StitchedArtifact`
5. `StitchedReplayInput`
6. `NextWindowHint / WalkForwardResult`

本卷消费：

1. `WarmupRequirements`
2. `TimeProjectionIndex`
3. `DataPack / ResultPack`

本卷不负责：

1. segmented replay kernel
2. schedule policy / schema contract
3. 最终 stitched backtest 真值的 replay 算法与 contract 定义

本卷保持流程主线，因为 WF 的核心复杂度仍然是“规划 -> 窗口执行 -> stitched 组装”这条阶段链；对象化的作用是收住真值归属，不是把流程拆散。

本卷同时保留 WF 的顶层公共边界：

1. 正式输入是 `config: &WalkForwardConfig`
2. 正式总返回是 `WalkForwardResult`
3. `WalkForwardPlan / WindowArtifact / StitchedReplayInput` 都是这条公共输入输出 contract 内部的阶段对象
4. `03` 定义的 `RunArtifact` 边界只在本卷的测试侧同源 `DataPack / ResultPack` 路径上复用，不扩展到训练阶段

`WF` 入口 readiness 边界：

1. `WF` 入口 readiness guard 与 indicator source subset 校验，以 [06_fetched_live_formal_producer_and_wf_readiness.md](./06_fetched_live_formal_producer_and_wf_readiness.md) 为准。
2. 该 guard 是 consumer-side invariant assertion，不替代 fetched / live producer 接回 planner lifecycle。

## 分卷地图

### [04_walk_forward_and_stitched_1_windowing_and_injection.md](./04_walk_forward_and_stitched_1_windowing_and_injection.md)

负责：

1. `WalkForwardPlan`
2. `WindowIndices / WindowSliceIndices`
3. `slice_data_pack_by_base_window(...)`
4. 跨窗信号注入

### [04_walk_forward_and_stitched_2_window_execution_and_return.md](./04_walk_forward_and_stitched_2_window_execution_and_return.md)

负责：

1. 每个窗口的执行流程
2. `WindowArtifact / WalkForwardResult / StitchedArtifact`
3. `StitchedReplayInput` 的对象定义、返回落点与 `NextWindowHint`

### [04_walk_forward_and_stitched_3_stitched_algorithm.md](./04_walk_forward_and_stitched_3_stitched_algorithm.md)

负责：

1. stitched 正式上游输入
2. `stitched_data`
3. `stitched_signals / backtest_schedule / stitched_atr_by_row / stitched_indicators_with_time`
4. `StitchedReplayInput` 的构造算法与字段来源

## stitched 单一事实块

涉及 stitched 输入边界时，统一以这 3 条为准；后续分卷只写各自消费后的结论，不再平行定义第二套口径。

1. `StitchedReplayInput` 的正式字段固定为：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
   - `stitched_indicators_with_time`
2. `backtest_schedule` 的单一来源固定为：
   - 各窗口 `window_results[i].meta.test_active_base_row_range`
   - stitched 阶段只允许对这份绝对 base 半开区间做减法重基
3. stitched 正式信号语义固定为：
   - 直接消费各窗口 `test_active_result.signals`
   - 跨窗 carry 开仓写在 active 第一根
   - 继承开仓在第二根 active bar 开盘执行
   - 这是当前 stitched 输入行轴上的唯一正式语义

## 阅读提醒

1. `04` 真正直接消费的是 `W_required[k]`，但真正落地到切片与重基时，只能认当前窗口的 `warmup_by_key[k]` 与最终 `ranges[k].warmup_bars`。
2. `WindowSliceIndices` 是本卷使用的正式名字；它承担窗口切片计划对象角色，不再平行引入第二套同义命名。
3. `04` 负责 stitched orchestration：
   - 准备 `StitchedReplayInput`
   - 调用 `05`
   - 回收最终 `StitchedArtifact`
   `05` 负责定义并执行正式 stitched backtest 真值的 segmented replay 算法与 contract。
