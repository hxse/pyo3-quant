# 向前滚动测试设计理念（精简版）

> 本文只描述理念、硬约束与职责边界。
> 详细实现以任务文档为准：`doc/tasks/2026-02-27 wf warmup minimal/01_summary/task_summary.md`。

## 1. 核心目标

Walk-Forward 的目标不是“跑通流程”，而是得到**口径稳定、可解释、可复现**的样本外评估结果。

重点解决两类偏差：

1. 指标前导 NaN 导致测试期前段空仓。
2. 窗口切换导致仓位与状态断裂。

## 2. 基本窗口模型

每个窗口固定三段：

1. `train`
2. `transition`
3. `test`

执行原则：

1. 训练段只用于优化。
2. 评估段使用 `transition + test` 连续回测。
3. 只对 `test` 计分与拼接。

## 3. 关键硬约束

1. 滚动步长固定等于 `test` 长度（禁止 `step_ratio`）。
2. 过渡段不计分，只用于预热与状态衔接。
3. 只拼接测试段（禁止拼接过渡段）。
4. `transition_bars` 必须大于 0（本设计不支持无过渡段）。
5. 窗口参数统一使用固定 bar 数（`train_bars/transition_bars/test_bars`），禁止按比例切窗。
6. 多周期 mapping 统一由 Rust `data_ops` 处理，禁止 Python 侧重复实现。
7. 数据不足、窗口非法、映射越界、拼接冲突一律直接报错（fail-fast）。
8. `wf_warmup_mode` 仅允许三种：`BorrowFromTrain` / `ExtendTest` / `NoWarmup`。
9. `test_bars >= 2`（保证测试段倒数第二根注入位存在）。
10. `BorrowFromTrain` 额外要求 `effective_transition_bars <= train_bars`。

`effective_transition_bars` 口径：
1. `BorrowFromTrain/ExtendTest`：`max(indicator_warmup_bars_base, transition_bars, 1)`。
2. `NoWarmup`：`max(transition_bars, 1)`。

## 4. 执行链路（性能口径）

固定链路：

1. `walk_forward` 调 Rust 优化器，在训练段并发评估参数。
2. 每窗口得到最优参数后，第一遍只跑 `ExecutionStage::Signals`（`transition + test`）。
3. 注入信号后再跑 `Backtest -> Performance`。
4. 跨窗判定源固定使用“上一窗口测试段末根”。
3. 裁切 `test` 后进入窗口结果与全局拼接结果。

性能边界：

1. 并发只发生在训练优化阶段。
2. 评估阶段第一遍停在 `Signals`，避免重复完整回测。
3. 第二遍才执行完整 `Backtest/Performance`。

## 5. 输出口径（理念层）

Walk-Forward 输出必须同时支持：

1. 窗口级审计（每窗口参数、范围、指标）。
2. 全局样本外评估（拼接后曲线与聚合指标）。
3. 实盘对接提醒（滚动频率与下次窗口预测）。

主评估指标优先级：

1. `walk_forward.calmar_ratio_raw`（最优先）
2. `walk_forward.total_return`
3. `walk_forward.max_drawdown`
4. `walk_forward.calmar_ratio`（辅助参考）

优先 `calmar_ratio_raw` 的原因：

1. 与优化器目标口径保持一致，减少阶段间口径漂移。
2. `calmar_ratio` 含年化，在小样本窗口上更容易放大波动。
3. 同资产、同周期横向比较时，`calmar_ratio_raw` 更稳定直接。

审计与对接字段（必须）：

1. `rolling_every_days`（多少天滚动一次）
2. `next_window_hint`（下次窗口大概日期预测）

时间口径：

1. 返回字段统一使用 `time` 毫秒级时间戳（UTC ms）。
2. 日期显示由上层按 UTC 转换，不在核心计算层混入字符串时间。

## 6. Rust / Python 职责边界

Rust 负责：

1. 窗口切分、优化、评估、拼接、聚合统计。
2. 统一产出可复现结果。

Python 负责：

1. 阶段编排与阈值控制。
2. CLI 与 notebook 展示。

禁止事项：

1. Python 侧二次实现 Rust 已定义口径。
2. Python 侧静默修复或回退逻辑。

## 7. 与详细实现文档的关系

本文只保留“为什么与约束”。以下内容统一迁移到详细实现文档：

1. 边界信号注入规则与时序。
2. `DataContainer / BacktestSummary` 切片与拼接算法。
3. 资金列重建与绩效重算流程。
4. 窗口级与拼接级完整返回对象字段定义。

请以 `doc/tasks/2026-02-27 wf warmup minimal/01_summary/task_summary.md` 作为实现依据。

## 8. 一句话总结

Walk-Forward 的唯一目标是：在严格口径下，把“训练优化后的样本外表现”稳定、可解释地量化出来，而不是追求表面可运行。

## 9. 实盘推荐 bars 模板

以下是可直接落地的初始模板（固定 bar 口径，按 `24/7` 市场）：

目标口径：

1. `test_bars` 约等于 30 天（约 1 个月）
2. `transition_bars` 约等于 30 天（保证边界衔接）
3. `train_bars` 约等于 180 天（约 6 个月训练样本）

1. `15m`（高频短线，重训更频繁）
   - `train_bars = 17280`（约 180 天）
   - `transition_bars = 2880`（约 30 天）
   - `test_bars = 2880`（约 30 天，建议每月滚动一次）
2. `30m`（中短线，研究与实盘常用）
   - `train_bars = 8640`（约 180 天）
   - `transition_bars = 1440`（约 30 天）
   - `test_bars = 1440`（约 30 天，建议每月滚动一次）
3. `1h`（中线，重训频率更低）
   - `train_bars = 4320`（约 180 天）
   - `transition_bars = 720`（约 30 天）
   - `test_bars = 720`（约 30 天，建议每月滚动一次）

实盘调参顺序建议（固定流程）：

1. 先固定 `train_bars` 与 `transition_bars`，只调 `test_bars`（决定滚动频率）。
2. 再微调 `transition_bars`（优先保证边界状态衔接稳定）。
3. 最后再调整 `train_bars`（控制参数学习稳定性与响应速度平衡）。

说明：

1. 模板是起点，不是最优值；最终以 `walk_forward.calmar_ratio_raw` 为主排序依据。
2. 所有窗口长度必须与策略持仓周期匹配，禁止盲目套用。
3. 若不是 `24/7` 市场（如股票有休市），应按真实交易时长重算 bars，不要机械沿用以上数值。
