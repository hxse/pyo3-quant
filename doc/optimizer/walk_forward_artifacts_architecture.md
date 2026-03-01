# Walk-Forward 完整产物返回架构（当前实现）

本文档是当前 WF 产物与执行链的实现口径说明。

范围：
1. 只描述当前代码已落地行为。
2. 不讨论历史迁移与兼容层。
3. 与实现冲突时，以源码为准（`src/backtest_engine/walk_forward/*.rs`、`src/types/outputs/walk_forward.rs`）。

---

## 1. 目标与边界

目标：
1. 返回可直接绘图、可直接评估、可直接审计的完整 WF 结果。
2. 同时保留窗口级结果和全局 stitched 结果。
3. 保持回测主链不重构，只在 WF 内完成窗口编排与注入。

边界：
1. 本方案保留 `Train/Transition/Test` 三段。
2. `Transition` 只用于指标预热与注入锚点，不计入测试绩效。
3. 滚动步长固定等于 `test_bars`。

---

## 2. 输入与输出契约

输入：
1. `DataContainer`
2. `SingleParamSet`
3. `TemplateContainer`
4. `SettingContainer`
5. `WalkForwardConfig`

输出：
1. `WalkForwardResult.optimize_metric`
2. `WalkForwardResult.window_results: Vec<WindowArtifact>`
3. `WalkForwardResult.stitched_result: StitchedArtifact`

`WindowArtifact` 当前字段（与代码一致）：
1. `data`, `summary`
2. `time_range`, `bar_range`, `span_ms`, `span_days`, `span_months`, `bars`
3. `window_id`, `train_range`, `transition_range`, `test_range`
4. `best_params`, `optimize_metric`, `has_cross_boundary_position`

`StitchedArtifact` 当前字段（与代码一致）：
1. `data`, `summary`
2. `time_range`, `bar_range`, `span_ms`, `span_days`, `span_months`, `bars`
3. `window_count`, `first_test_time_ms`, `last_test_time_ms`
4. `rolling_every_days`, `next_window_hint`

说明：
1. `window_results` 只保留各窗口 `Test` 段产物。
2. `stitched_result` 由所有窗口 `Test` 段按时间顺序拼接。

---

## 3. 配置与运行时派生值

`WalkForwardConfig` 关键参数：
1. `train_bars`
2. `transition_bars`
3. `test_bars`
4. `wf_warmup_mode`（`BorrowFromTrain | ExtendTest | NoWarmup`）
5. `inherit_prior`
6. `optimizer_config`

运行时先根据指标契约聚合拿到：
1. `indicator_warmup_bars_base`

再派生：
1. `BorrowFromTrain/ExtendTest`：
`effective_transition_bars = max(indicator_warmup_bars_base, transition_bars, 1)`
2. `NoWarmup`：
`effective_transition_bars = max(transition_bars, 1)`

硬约束：
1. `transition_bars >= 1`
2. `test_bars >= 2`
3. `effective_transition_bars >= 1`
4. `BorrowFromTrain` 下 `effective_transition_bars <= train_bars`

---

## 4. 三种窗口切分公式

统一符号：
1. `N`：base 总行数
2. `T`：`train_bars`
3. `E`：`effective_transition_bars`
4. `S`：`test_bars`
5. `step = S`
6. 第 `i` 个窗口起点：`base_start_i = i * step`

### 4.1 BorrowFromTrain

1. `Train_i = [base_start_i, base_start_i + T)`
2. `Transition_i = [base_start_i + T - E, base_start_i + T)`（与训练尾部重叠）
3. `Test_i = [base_start_i + T, base_start_i + T + S)`
4. 合法性：`base_start_i + T + S <= N`

### 4.2 ExtendTest

1. `Train_i = [base_start_i, base_start_i + T)`
2. `Transition_i = [base_start_i + T, base_start_i + T + E)`
3. `Test_i = [base_start_i + T + E, base_start_i + T + E + S)`
4. 合法性：`base_start_i + T + E + S <= N`

### 4.3 NoWarmup

1. 区间公式与 `ExtendTest` 相同。
2. 差异仅在 `E` 的来源不使用 `indicator_warmup_bars_base` 放大。

---

## 5. 每窗口执行链（固定顺序）

每窗口固定顺序：
1. 切 `Train_i`，执行优化得到 `best_params_i`。
2. 切 `test_with_warmup_data = Transition_i + Test_i`。
3. 第一遍评估只跑 `ExecutionStage::Signals`，得到基线 `signals`。
4. 基于跨窗状态注入信号。
5. 第二遍评估复用第一遍 `indicators`，替换注入后 `signals`，执行 `Backtest`。
6. 从第二遍结果切出 `Test_i` 形成窗口正式产物。
7. 对窗口 `Test_i` 重新计算窗口绩效并写回 `summary.performance`。

说明：
1. 第一遍不跑完整回测链，目的只是拿“可注入基线信号”。
2. 第二遍才是窗口正式回测结果来源。

---

## 6. 跨窗判定与信号注入规则

跨窗判定来源：
1. 固定使用“上一窗口 `Test` 末根持仓状态”。
2. 第一窗口没有上一窗口，默认无跨窗持仓。

判定口径：
1. 多头跨窗：`entry_long_price` 非空且 `exit_long_price` 为空。
2. 空头跨窗：`entry_short_price` 非空且 `exit_short_price` 为空。
3. 同根多空同时成立直接报错。

注入规则（按顺序）：
1. 在当前窗口 `Test` 倒数第二根注入双向离场。
2. 如果跨窗成立，在当前窗口 `Transition` 最后一根注入同向开仓。
3. 如果不跨窗，不注入开仓。

明确禁止：
1. 禁止在 `Transition` 倒数第二根注入离场（旧逻辑已废弃）。
2. 禁止用“当前窗口首跑回测结果”判定跨窗。

---

## 7. stitched 构建口径

1. 把所有窗口 `Test` 段 `summary` 串联拼接。
2. 生成 `stitched_data` 与 `stitched_summary`。
3. 按窗口边界重建 stitched 资金列。
4. 基于 `stitched_data + stitched_backtest` 重新计算 stitched 绩效。

校验：
1. stitched base 时间必须严格递增。
2. 非 base source 时间必须非递减。
3. stitched 行数必须与窗口测试段累计行数一致。

---

## 8. Fail-Fast 清单

任一条件失败直接报错：
1. 窗口参数非法（如 `test_bars < 2`）。
2. `BorrowFromTrain` 下 `E > T`。
3. 窗口越界导致无法生成窗口。
4. 跨窗多空冲突。
5. 切片长度或 stitched 长度不一致。
6. stitched 时间序列不满足单调性约束。

---

## 9. Python 工作流要求

1. `walk_forward` 前必须显式调用一次 `validate_wf_indicator_readiness(...)`。
2. pipeline、searcher、demo.ipynb 都遵循“预检一次 -> 正式 WF”顺序。
3. Python 侧不重写窗口算法和注入算法。

---

## 10. 一句话总结

当前实现是“保留三段窗口 + 指标契约驱动过渡长度 + 上一窗测试末根判定跨窗 + 双阶段评估（Signals/Backtest）+ stitched 重建资金列”的统一口径。
