# 向前滚动测试设计理念（过渡期版）

> 核心目标：在不过度工程化的前提下，让 Walk-Forward 更贴近实盘切参流程，降低窗口切换带来的评估偏差。

## 1. 解决的问题

传统 Walk-Forward 直接“训练 -> 测试”容易出现两类偏差：

1. 指标前导 NaN 导致测试期前段空仓，影响评估公平性。
2. 窗口切换时仓位/状态断裂，导致测试期早段表现失真。

因此本方案引入 **过渡期（Transition）**。

## 2. 窗口定义

每个窗口包含三段时间：

1. 训练期（Train）
2. 过渡期（Transition）
3. 测试期（Test）

但执行上只做两次回测：

1. 用训练期做参数优化（得到本窗口最优参数）
2. 用“过渡期+测试期”做一次连续回测（参数固定为训练最优）

说明：过渡期与测试期参数完全一致，不在过渡期二次优化。
实现口径（强约束）：过渡期与测试期必须来自同一次连续回测结果，再从中裁切测试期；禁止把过渡期与测试期拆成两次独立回测。

### 2.1 执行链路（性能关键）

Walk-Forward 的核心执行链路是：

1. `walk_forward` 调用 Rust 优化器（训练期）。
2. 优化器在训练期内并发评估多组参数（内部调用回测引擎）。
3. 训练期得到该窗口最优参数后，仅对“过渡期+测试期”做一次连续回测（单次）。
4. 从该单次连续回测中裁切测试期并产出测试指标。
5. 按时间顺序拼接各窗口测试期净值数据，并统一返回全局拼接曲线与窗口/全局评估报告。

这条链路是性能与口径一致性的关键：训练期“多次并发”，评估期“单次验证”。

## 3. 评估口径（强约束）

1. 过渡期不计分，只用于预热与状态衔接。
2. 只评估测试期指标。
3. 全局样本外拼接时，只拼接测试期利润/收益序列，不拼接过渡期。
4. 滚动步长固定等于测试期长度，保证测试期拼接无重叠、无断档。

这四条是本设计的硬约束。

## 4. 为什么这样设计

1. 避免前导 NaN 造成的测试期空仓偏差。
2. 降低参数切换瞬间导致的仓位断裂影响。
3. 让测试期更接近“参数上线后稳定运行”的真实表现。

## 5. 窗口滚动示例

示例（按月）：

1. 训练 1-6，过渡 7，测试 8
2. 训练 2-7，过渡 8，测试 9
3. 训练 3-8，过渡 9，测试 10

每个窗口都遵循“训练优化一次 + 过渡期和测试期连续回测一次”。

## 6. 配置建议

保留现有配置：

1. `train_ratio`
2. `transition_ratio`
3. `test_ratio`
4. `inherit_prior`

执行规则（硬约束）：

1. 不再提供 `step_ratio`，滚动步长固定等于 `test_ratio` 对应长度。
2. `evaluate_test_only=true`（固定为 true）
3. `stitch_test_only=true`（固定为 true）

默认建议：

1. 过渡期可先从 1 个自然周期开始（如 15m 策略先用 1~3 天）。
2. 数据不足时直接报错，不允许自动退化到 `transition=0`。

## 7. 输出结果建议

每窗口至少输出：

1. 训练最优参数
2. 测试期指标（不含过渡期）
3. 过渡期长度（用于审计）
4. 窗口级字段清单（建议固定）：`window_id / train_range / transition_range / test_range / best_params / train_metrics / test_metrics`

全局汇总至少输出：

1. 测试期拼接后的总收益指标
2. 窗口级测试指标分布（均值/中位数/最差窗口）
3. 测试期拼接收益曲线（用于可视化）

### 7.1 测试期拼接算法（强约束）

为避免窗口重置导致的高估/低估，拼接逻辑采用“收益率拼接 + 复利重建”：

1. 对每个窗口，先跑“过渡期+测试期”一次连续回测（同一组最优参数）。
2. 在该连续区间上计算逐 bar 收益率序列 `r_t = equity_t / equity_{t-1} - 1`。
3. 仅截取测试期对应的 `r_t`，过渡期收益不参与拼接。
4. 按时间顺序拼接所有窗口测试期 `r_t`，得到全局 OOS 收益率序列 `R`。
5. 用复利重建全局 OOS 资金曲线：
   - `V_0 = 1.0`
   - `V_t = V_{t-1} * (1 + R_t)`

说明：

1. 这是复利口径，不是线性相加口径。
2. 禁止直接拼接各窗口 `equity` 水平值，也禁止把各窗口总收益直接相加。
3. 若测试区间存在重叠，默认直接报错，不做静默覆盖。

### 7.2 最小可视化输出

拼接后用于可视化的最小输出结构：

1. `time`
2. `equity`

`time + equity` 两列即可完成主图展示与后续绩效分析。
时间口径约束：`time` 使用 UTC 毫秒时间戳（ms）。

## 8. 接口职责与返回口径（Rust 优先）

为避免 Python 端重复加工导致口径漂移，Walk-Forward 采用“Rust 计算、Python 编排展示”的职责分层。

1. Rust 端职责（必须）：
   - 窗口切分、训练优化、过渡期+测试期连续回测。
   - 仅截取测试期收益序列并完成全局拼接。
   - 复利重建全局 OOS 资金曲线（`time + equity`）。
   - 统一产出窗口级指标、全局聚合指标、分布统计（如 mean/median/p05/p95）。
2. Python 端职责（最小化）：
   - 分阶段流程控制（是否继续下一阶段）。
   - 结果展示（CLI 文本、notebook 可视化）。
   - 不重复计算 Rust 已产出的统计。
3. 错误策略（强约束）：
   - 数据不足、窗口重叠、无效配置一律直接报错。
   - 禁止静默降级与隐式回退。
4. 并发口径（强约束）：
   - 并发发生在训练期优化采样阶段（多参数并行评估）。
   - 过渡期+测试期评估阶段固定为单次连续回测，不做并发重复评估。

### 8.1 建议返回结构

1. 每窗口：
   - `train_range` / `transition_range` / `test_range`
   - `best_params`
   - `train_metrics` / `test_metrics`
   - `test_returns`（仅测试期）
   - `test_times`
2. 全局：
   - `aggregate_test_metrics`（基于拼接后 OOS 曲线）
   - `window_metric_stats`（跨窗口分布统计）
   - `stitched_time`
   - `stitched_equity`

说明：`optimize_metric` 应保持强类型枚举，避免字符串二次解释。

### 8.2 面向 AI 评估的最小充分返回集

为支持 AI 基于返回结果做“是否继续下一阶段”的判断，建议统一采用以下返回口径，并尽量由 Rust 端直接产出：

1. Backtest：
   - 核心绩效：`total_return / calmar_ratio / max_drawdown`
   - 交易统计：`total_trades / win_rate / profit_factor / expectancy`
   - 数据质量：`bars_used / warmup_bars / skipped_bars`
2. Optimize：
   - `optimize_metric / optimize_value`
   - `top_k_samples`（参数 + 目标值）
   - 收敛轨迹（每轮 `best/mean/std`）
   - 失败统计（`invalid_samples / failed_backtests`）
3. Sensitivity：
   - `original / mean / std / cv`
   - 分位数：`p05 / p25 / p50 / p75 / p95`
   - 极值：`min / max`
4. Walk-Forward：
   - 窗口明细：`train_range / transition_range / test_range`
   - 窗口指标：`train_metrics / test_metrics / gap(train-test)`
   - 全局拼接曲线：`stitched_time + stitched_equity`
   - 分布统计：`mean / median / std / p05 / p95 / min / max`
   - 关键窗口：`best_window_id / worst_window_id`
5. 复现元数据（所有阶段共享）：
   - `seed / symbol / timeframe / data_source`
   - `config_hash / data_hash / engine_version`
   - `elapsed_ms`

说明：

1. Python 端不应重算上述统计，仅负责读取、阈值判断、展示。
2. 若 Rust 已返回完整统计，Python 层禁止再做“同口径二次实现”，避免口径漂移。
3. 指标口径约束：`total_return` 使用小数口径（例如 `0.25` 表示 `+25%`），禁止在返回层混用百分数字符串。

## 9. 设计边界

1. 本设计不追求复杂状态恢复系统。
2. 本设计不把过渡期纳入绩效评分。
3. 本设计优先保证评估口径一致、可解释、可复现。

## 10. 一句话总结

Walk-Forward 采用“训练优化 + 过渡期与测试期连续回测”，并坚持“只评估测试期、只拼接测试期利润”，以获得更接近实盘切参过程的样本外评估。
