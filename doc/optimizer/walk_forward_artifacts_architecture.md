# Walk-Forward 完整产物返回架构（详细设计）

> 目标：在不引入脏兼容层的前提下，让 Walk-Forward 返回“可直接画图、可直接评估、可直接审计”的完整对象。
> 约束：破坏性更新，不兼容旧返回口径。

## 1. 设计目标

本设计要同时满足两类消费方：

1. 研究与调试：需要看每个窗口的独立结果（窗口内回测图、指标、参数）。
2. 汇总评估：需要看拼接后的全局样本外结果（统一曲线、统一绩效、统一报告）。

因此返回分为两层：

1. `window_results[]`：窗口级完整产物数组。
2. `stitched_result`：全局拼接完整产物对象。

返回顺序硬约束：

1. `window_results[]` 必须按时间自然顺序返回（等价按 `window_id` 递增）。
2. 禁止为了“最优/最差窗口”计算而重排 `window_results[]`。
3. `best_window_id / worst_window_id` 仅作为索引信息返回，不改变窗口数组顺序。

两层都必须带：

1. `DataContainer`（用于 OHLC 与多周期 source 绘图，含 mapping 语义）。
2. `BacktestSummary`（用于指标、净值、开平仓、止损止盈等绘图与绩效分析）。
3. 额外窗口信息（范围、时长、bar 数等审计字段）。

## 2. 术语定义

每个窗口由三段组成：

1. `train`：训练优化段
2. `transition`：过渡段
3. `test`：测试段

执行口径固定：

1. 训练段用于优化（多次并发评估）。
2. 评估段使用 `transition + test` 连续回测（单次）。
3. 只对 `test` 计分。
4. `transition_ratio` 必须大于 0（本设计不支持无过渡段）。

## 3. 返回对象模型（抽象）

返回模型采用“组件组合”方式，而不是大一统枚举。

### 3.1 CorePayload（统一核心载荷）

所有 WF 产物都共享同一核心：

1. `data: DataContainer`（绘图与时序基准）
2. `summary: BacktestSummary`（指标/信号/回测/绩效统一容器）

约束：

1. `data` 与 `summary` 必须时间对齐。
2. `summary` 必须可直接用于绘图与绩效分析，不依赖外部补列。

### 3.2 RangeIdentity（统一范围身份）

所有产物共享同一“范围身份”：

1. `time_range`（UTC ms）
2. `bar_range`（base 语义）
3. `span`（ms/days/months）
4. `bars`（覆盖条数）

### 3.3 WindowContext（窗口语义）

窗口级上下文：

1. `window_id`
2. `train_range / transition_range / test_range`
3. `best_params`
4. `optimize_metric`
5. `has_cross_boundary_position`

### 3.4 StitchContext（拼接语义）

拼接级上下文：

1. `window_count`
2. `first_test_time_ms / last_test_time_ms`

### 3.5 ScheduleHint（调度提示）

仅拼接级使用的调度信息：

1. `rolling_every_days`
2. `next_window_hint`

`next_window_hint` 抽象定义：

1. 时间预测：下个窗口各关键时间点（train/transition/test/ready）。
2. 剩余时间：距离“可完整评估时间”的剩余量（如 `eta_days`）。
3. 推导上下文：推导依据窗口（如 `based_on_window_id`）。

### 3.6 最终组合

`WindowArtifact = CorePayload + RangeIdentity + WindowContext`

`StitchedArtifact = CorePayload + RangeIdentity + StitchContext + ScheduleHint`

语义：

1. `WindowArtifact` 只表达“单窗口 test 段”的完整结果。
2. 用于窗口级绘图、窗口级诊断、窗口级回归。
3. `StitchedArtifact` 表示“全局样本外 test 拼接”的完整结果。
4. 用于全局评估、策略排序、实盘重算提醒。

### 3.7 最小字段表（实现门槛）

#### WindowArtifact 最小字段

| 组件 | 字段 | 必须 | 说明 |
|---|---|---|---|
| `CorePayload` | `data` | 是 | `DataContainer`（窗口 test 段） |
| `CorePayload` | `summary` | 是 | `BacktestSummary`（窗口 test 段） |
| `RangeIdentity` | `time_range` | 是 | `(start_time_ms, end_time_ms)` |
| `RangeIdentity` | `bar_range` | 是 | `(start_bar, end_bar)` |
| `RangeIdentity` | `span` | 是 | `span_ms/span_days/span_months` |
| `RangeIdentity` | `bars` | 是 | 覆盖 bar 数 |
| `WindowContext` | `window_id` | 是 | 窗口编号 |
| `WindowContext` | `train_range/transition_range/test_range` | 是 | 训练/过渡/测试范围 |
| `WindowContext` | `best_params` | 是 | `SingleParamSet` |
| `WindowContext` | `optimize_metric` | 是 | 优化目标 |
| `WindowContext` | `has_cross_boundary_position` | 是 | 是否跨过渡-测试持仓 |

#### StitchedArtifact 最小字段

| 组件 | 字段 | 必须 | 说明 |
|---|---|---|---|
| `CorePayload` | `data` | 是 | `DataContainer`（全局 test 连续切片） |
| `CorePayload` | `summary` | 是 | `BacktestSummary`（全局拼接） |
| `RangeIdentity` | `time_range` | 是 | `(first_test_time_ms, last_test_time_ms)` |
| `RangeIdentity` | `bar_range` | 是 | 全局覆盖 bar 范围 |
| `RangeIdentity` | `span` | 是 | `span_ms/span_days/span_months` |
| `RangeIdentity` | `bars` | 是 | 全局覆盖 bar 数 |
| `StitchContext` | `window_count` | 是 | 窗口总数 |
| `ScheduleHint` | `rolling_every_days` | 是 | 滚动频率（天） |
| `ScheduleHint` | `next_window_hint` | 是 | 下次窗口预测 |

## 4. 单窗口算法（核心）

以下流程对每个窗口独立执行。

### 4.1 训练优化

1. 从原始 `DataContainer` 切 `train`。
2. 调 `run_optimization(...)` 拿到 `best_params`。

### 4.2 第一次评估（用于边界诊断）

1. 切 `transition + test` 数据。
2. 用 `best_params` 调 `execute_single_backtest`，拿到 `BacktestSummary`。
3. 第一次评估必须使用 `return_only_final=false`，确保 `indicators/signals/backtest/performance` 可用于第二次评估。
4. 读取：
   - `summary.signals`：用于信号注入基准。
   - `summary.backtest`：用于检测边界是否存在跨段持仓。

`has_cross_boundary_position` 检测口径（基于 `transition` 最后一根）：

1. 若 `entry_long_price` 非 NaN 且 `exit_long_price` 为 NaN -> 跨边界多头。
2. 若 `entry_short_price` 非 NaN 且 `exit_short_price` 为 NaN -> 跨边界空头。
3. 否则 -> 无跨边界持仓。

### 4.3 边界信号注入（固定规则）

目标：窗口边界可控，拼接口径稳定。

固定注入点（信号写入 `signals_df`）：

1. `transition` 倒数第 2 根：强制离场信号（exit）。
2. `test` 倒数第 2 根：强制离场信号（exit）。
3. 若检测到“跨 transition->test 持仓”：在 `transition` 最后一根注入同向进场信号（entry）。

说明：

1. 回测引擎是 next-bar 执行，信号在 `bar[i-1]`，执行在 `bar[i].open`。
2. 因此上述位置选择是为了在边界 bar 开盘完成切换。
3. `signal_preprocessor` 可能屏蔽部分 `entry`，本设计接受这一行为，不额外加复杂绕过逻辑。
4. 离场注入采用“全平”语义：`exit_long=true` 且 `exit_short=true`（不依赖方向判定）。
5. 进场注入必须先判定当前持仓方向（long/short），只允许写入对应方向的 `entry_*`，禁止双向同时进场。
6. 若同一 bar 同时出现 `entry_*` 与 `exit_*`，预处理会抑制进场（exit 优先）；此时可能出现 `has_cross_boundary_position=true` 但测试段仍以空仓开始，这属于预期行为。
   - 清洗入口：`PreparedData::new(...)` 内调用 `signal_preprocessor::preprocess_signals(...)`。

### 4.3.1 过渡期开仓钳制（强制）

为减少过渡期对测试期资金与手续费口径的污染，Walk-Forward 必须启用“过渡期开仓钳制”：

1. 过渡期内的 `entry_*` 全部强制置 `false`。
2. 仅在检测到跨边界同向持仓时，允许在过渡期最后一根写入同向 `entry_* = true`（反向 `entry_* = false`）。
3. 离场注入规则不变（全平语义）。

该策略的用处：

1. 过渡期不再引入新交易，测试期起始资金口径更稳定。
2. `window_results[]` 的资金/手续费语义更干净，通常无需额外窗口级资金重建。
3. `stitched_result` 仍做全局资金曲线处理，但手续费语义更稳定、实现复杂度更低。

设计边界：

1. 这是 WF 的评估规则，不是原始策略信号的完整还原。
2. 过渡期最后一根同向进场仍可能被 `signal_preprocessor` 抑制（预期行为）。

### 4.4 第二次评估（边界修正后正式结果）

1. 目标：在同一 `transition + test` 数据上，用“注入后的 `signals_df`”得到正式评估结果。
2. 约束：不引入新 API，走手动链路；且使用新执行上下文（不复用第一次上下文实例）。
3. 固定步骤：
   - 复用第一次评估产出的 `indicators`
   - 替换为注入后的 `signals_df`
   - 执行回测阶段（等价 `execute_backtest_if_needed(...)`）
   - 产出第二次 `BacktestSummary`（以 `backtest` 为核心）
4. 第二次评估不调用 `execute_indicator_if_needed(...)`。
5. 第二次评估结果是窗口正式结果来源。

### 4.5 生成窗口产物

1. 从第二次评估结果中切出 test 段 `BacktestSummary`。
2. 使用 `data_ops` 切出同范围 test 段 `DataContainer`。
3. 基于 test-only 的 `data + backtest` 重算 `summary.performance`。
4. 禁止沿用 `transition+test` 的绩效到窗口最终结果。
5. 由于“过渡期开仓钳制”为强制规则，窗口级不再做额外资金重建（沿用 test 段资金列）。
6. 即使窗口级不重建，仍必须执行资金合法性校验（包含 test 首 bar）：
   - 若出现 `NaN/Inf/<0`，直接报错（fail-fast）。
   - 不允许以“窗口级不重建”为由跳过资金列校验。
7. 组装 `WindowArtifact`。
8. `WindowArtifact` 写入 `window_results[]` 时必须保持窗口自然时间顺序（禁止插入式重排）。

### 4.6 `return_only_final` 使用策略（独立约束）

1. 优化器训练采样阶段：`return_only_final=true`
   说明：该阶段并发量大，只需要最终绩效值，保留中间 DataFrame 会明显放大内存占用。
2. `(transition + test)` 评估阶段（第一次与第二次）：`return_only_final=false`
   说明：此阶段需要 `indicators/signals/backtest/performance` 完整对象用于注入、切片、拼接、绘图与审计。
3. 两者按阶段分工，不可混用。

## 5. 全局拼接算法（核心）

## 5.1 数据切片与拼接边界

由于 WF 固定 `step_len = test_len`，各 test 段时间上应连续且不重叠。

全局数据获取：

1. `DataContainer`：不拼接，只做一次“全局 test 连续区间切片”。
   - 说明：`DataContainer` 内每个 df（含多周期 source/indicators）都必须切片，并按 mapping 规则复用 `data_ops`。
2. `BacktestSummary`：先切窗口 test 段，再按窗口维度拼接。
   - 说明：由于窗口在原评估区间含重叠（transition+test），`BacktestSummary` 必须逐窗口切后再拼，不能直接全量拼。

对象级处理硬约束（必须）：

1. 处理单位是“完整对象”，不是单个表。
2. 对“分割过或拼接过”的对象，内部每个 DataFrame 都必须同步处理，禁止只处理部分表。
3. `DataContainer`：对象内每个 df 都必须完成窗口切片；不做拼接。
4. `BacktestSummary`：对象内每个 df 都必须先完成窗口切片，再参与拼接。

## 5.2 BacktestSummary 拼接规则

需要拼接以下组成：

1. `indicators`：按 key 逐个 `vstack`，schema 不一致直接报错。
2. `signals`：按时间 `vstack`。
3. `backtest`：按时间 `vstack`。
4. `performance`：不拼接旧值，基于拼接后的 `data + backtest` 重新计算。

术语说明（避免误解）：

1. `vstack`：按行向下拼接 DataFrame（vertical stack），不是按列横向拼接。
2. `schema`：DataFrame 的列结构定义，至少包含列名与列类型（实现上通常还要求列顺序一致）。
3. 本文中的“schema 不一致直接报错”是指：列名或类型不一致即失败，禁止自动补列、类型强转或静默对齐。

时间一致性校验（强约束）：

1. 拼接函数内部必须立即校验 `time` 严格递增且无重复（运行时硬校验）。
2. 若发现重复时间或非递增，直接报错并终止（fail-fast）。
3. 外部测试必须覆盖该校验：正常样例通过、重复时间报错、非递增报错（回归保障）。

补充约束：

1. 上述每个 df 都先做窗口级 test 切片，再参与拼接。
2. 多周期列与映射必须统一复用 `data_ops`，禁止在 walk_forward 内再写一套切片/映射逻辑。

## 5.3 资金列与绩效列处理

不直接沿用窗口局部资金列作为全局资金列。

原因：

1. 每个窗口是独立评估起点，窗口切片后资金起点不一致。
2. 直接拼接会导致全局资金曲线与回撤失真。

处理方式（唯一口径）：

1. 仅以拼接后的局部资金列（`balance_local / equity_local / fee`）统一重建全局资金列。
2. 重建后再跑一次统一绩效分析，写入全局 `summary.performance`。
3. 该重建要求主要用于 `stitched_result`；`window_results[]` 在强制过渡期开仓钳制下不再做额外重建。
4. 明确禁止“事件触发重放”路径，避免与资金列重建形成双口径并存。

备注：

1. 此处“复用”指**算法口径复用**（公式一致），不是直接复用 `BacktestState::calculate_capital` 的调用路径。
2. 数据处理函数统一放在 `src/backtest_engine/data_ops`，保持高内聚。
3. 实现为新函数（例如 `rebuild_capital_columns_for_stitched_backtest`），输入是 DataFrame 列，而非状态机上下文对象。

资金重建列清单（简化方案）：

1. 必须重建：`balance / equity / total_return_pct / fee_cum / current_drawdown`
2. 保留窗口拼接原值：`trade_pnl_pct / fee`

资金重建依赖输入（最小集合）：

1. 拼接后的局部资金列：`balance_local / equity_local / fee`
2. 初始锚点：`initial_capital`（或等价初始全局资金）

实现口径（简化重建，非状态机重放）：

1. 逐 bar 计算局部增长因子并重建全局曲线（核心思想）：
   - `growth_equity[i] = equity_local[i] / equity_local[i-1]`
   - `equity_global[i] = equity_global[i-1] * growth_equity[i]`
2. `balance` 同理基于局部 `balance` 相对变化重建全局 `balance`。
3. `total_return_pct` 与 `current_drawdown` 基于重建后的全局 `equity` 再计算。
4. `fee_cum` 基于拼接后的 `fee` 重新累计。
5. 公式必须与现有绩效口径一致，禁止引入另一套统计定义。

异常值约束（强约束）：

1. 若局部资金列出现 `NaN/Inf`，直接报错（fail-fast）。
2. 若局部资金列出现 `< 0`，直接报错（fail-fast）。
3. `= 0` 视为合法“资金归零终态”：
   - 全局资金一旦归零，后续资金列保持 0；
   - 不再继续做增长因子除法。
4. 若出现“分母为 0 且分子非 0”的增长因子计算场景，直接报错（数据不一致）。

本步骤修改范围（必须明确）：

1. 只覆盖重建列：`balance/equity/total_return_pct/fee_cum/current_drawdown`
2. 保留原值列：`trade_pnl_pct/fee`
3. 不修改事件与状态列：`entry_* / exit_* / frame_state / first_entry_side / risk_in_bar_direction`
4. 不修改止损止盈轨迹列：`sl_* / tp_* / tsl_* / atr`（这些列用于绘图与审计，保持原样）

最终绩效计算：

1. 在“重建后的 backtest_df + 对应 DataContainer”上调用 `performance_analyzer::analyze_performance(...)`。
2. `summary.performance` 以该结果为唯一来源，不拼接窗口旧绩效。
3. `performance_params` 作为“指标计算配置”使用（指标白名单/风险自由利率等），不是绩效结果本身。
4. stitched 绩效默认使用策略级固定 `performance_params`（与窗口 `best_params` 解耦且一致；理论上两者应相同，但使用全局配置语义更清晰且更安全）。

## 6. DataOps 复用与扩展边界

现有口径可复用：

1. `DataContainer` 的 mapping 切法（source + indicators 同语义）。
2. 窗口切片与映射重基逻辑。

需要新增的工具函数（建议也放 `data_ops`）：

1. `slice_backtest_summary_by_base_window`（需接收 mapping 语义，不能只按 base 盲切）
2. `concat_backtest_summaries`
3. `rebuild_capital_columns_for_stitched_backtest`（命名可调整）
4. `slice_all_dataframes_by_base_window`（覆盖 DataContainer 与 BacktestSummary 内所有 df 的统一切片入口，命名可调整）
5. 推荐统一入口：`slice_core_payload_by_base_window(data, summary, start, len) -> (data, summary)`

原则：

1. 非就地修改输入，返回新对象。
2. schema/长度不一致直接报错。
3. 不保留旧实现并行路径，唯一方式实现。

### 6.1 工具函数复用矩阵（切割/拼接）

为避免在 WF 模块里散落数据处理代码，工具函数按三层复用：

1. DataFrame 通用层（底层原子操作）：
   - `slice_df_by_row_range(df, start, len)`
   - `vstack_dfs_strict(dfs)`（含 schema 校验）
   - `assert_time_strictly_increasing(df, "time")`
2. 容器层（组合 DataFrame 工具）：
   - `slice_data_container_by_base_window(...)`（已有，继续复用）
   - `slice_backtest_summary_by_base_window(...)`（新增）
   - `concat_backtest_summaries(...)`（新增）
3. WF 编排层（业务流程，不做底层处理）：
   - `build_window_artifact(...)`
   - `build_stitched_artifact(...)`
   - 仅调用容器层，不直接操作单个 df

边界约束：

1. 切割与拼接的校验规则必须共用同一套工具（schema/time/fail-fast）。
2. `data_ops` 负责数据处理正确性，WF 负责流程编排与对象组装。
3. 禁止在 WF 内重复实现切片、拼接、时间校验逻辑。

内存说明：

1. Polars 的 `slice`/`vstack` 在多数场景可复用底层内存视图（零拷贝/低拷贝）。
2. `WindowArtifact` 的多窗口返回主要增加的是对象引用与元数据，不会按窗口线性深拷贝全部数据。

## 7. 额外信息与审计字段

窗口级与拼接级都要返回基础审计信息，至少包含：

1. 行号区间：`train/transition/test range`
2. 时间区间：`start_time_ms/end_time_ms/span_ms`
3. bar 数：`bars`
4. 参数：`SingleParamSet`
5. 性能主指标：`calmar_ratio_raw/total_return/max_drawdown`（`calmar_ratio` 仅辅助）
6. 滚动频率：`rolling_every_days`
7. 下次窗口预测：`next_window_hint`

指标主次口径（强约束）：

1. 策略排序优先看 `calmar_ratio_raw`。
2. `calmar_ratio`（年化）保留返回，但仅用于辅助解读，不作为主排序指标。
3. 这样可与优化器目标保持一致，并降低小样本年化漂移带来的误判。

时间口径（强约束）：

1. Rust 核心返回层所有时间字段统一为 `time` 毫秒级时间戳（UTC ms）。
2. Python 层按需把毫秒时间戳转换为 UTC 日期字符串（仅展示用途）。
3. Rust 返回结构中不新增日期字符串字段，避免口径混入展示逻辑。
4. 所有“时长/天数/月数”一律使用 `end_time_ms - start_time_ms` 计算，禁止使用 `bar_count * interval_ms` 估算。

`rolling_every_days` 计算口径（强约束）：

1. 取窗口时间边界：`rolling_span_ms = test_end_time_ms - test_start_time_ms`。
2. `rolling_every_days = rolling_span_ms / 86_400_000.0`。
3. 该口径天然覆盖节假日/停盘/缺失 bar 等非均匀时间间隔场景。

`next_window_hint` 计算口径（强约束）：

1. 基于最后一个窗口 `last_window` 推算。
2. 优先使用真实时间跨度推算：`rolling_span_ms = last_test_end_time_ms - last_test_start_time_ms`。
3. 下个窗口的测试段起点可记为：`expected_test_start_time_ms = last_test_end_time_ms`（窗口边界连续口径）。
4. 实盘提醒应使用“可完整评估时间”：
   - `expected_window_ready_time_ms = last_test_end_time_ms + rolling_span_ms`
   - `eta_days = rolling_span_ms / 86_400_000.0`（或基于当前最新数据时间再计算剩余天数）
5. 禁止用 `interval_ms * bars` 估算提醒时间，统一用时间戳差值口径。

实时运行语义（显式约束）：

1. Walk-Forward 允许最后一个窗口处于“测试段未完整”状态。
2. 最后窗口未完整是预期行为，不视为异常；若完整则通常已进入下一个窗口评估周期。
3. `next_window_hint` 的核心用途是给实盘侧提供“距离下一次完整窗口切换还剩多久”的提醒。
4. 实盘对接固定流程：`eta_days` 到达后，触发一次重新回测/优化，使用最新数据重算并切换到最新参数。

指标边界说明（WF 预期行为）：

1. 各窗口指标基于各自窗口数据和各自最优参数独立计算。
2. 因参数切换与上下文切换，窗口边界处指标曲线可不连续，这属于 Walk-Forward 预期行为，不视为错误。

## 8. 与绘图引擎的对齐

返回对象若满足：

1. 完整 `DataContainer`
2. 完整 `BacktestSummary`

则可直接复用现有绘图入口，无需单独做 WF 绘图特化。

## 9. 失败策略（强约束）

以下场景一律直接报错：

1. 窗口切片越界
2. 拼接时 schema 不一致
3. 拼接后时间不递增
4. 必需列缺失（如 backtest 资金重建依赖列）

不做静默回退，不做兼容分支。

## 10. 实施顺序建议

1. 先落对象结构与返回口径（WindowArtifact + StitchedArtifact）。
2. 再落“边界信号注入 + 二次评估”。
3. 再落 `BacktestSummary` 切片/拼接工具。
4. 最后接入资金列统一重建与全局绩效重算。

完成后，旧 WF 拼接逻辑可整体移除。

迁移路径（破坏性更新）：

1. 新增 `WindowArtifact / StitchedArtifact / WalkForwardArtifactsResult` 类型。
2. 新入口返回“窗口数组 + 拼接对象”完整结构。
3. 旧 `WalkForwardResult` 的窗口统计字段逐步迁移到新结构；确认调用方全部迁移后移除旧结构。
