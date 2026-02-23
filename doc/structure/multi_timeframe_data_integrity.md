# 多周期数据映射与未来数据泄露防护

本文档描述系统中多周期数据的映射机制，以及各模块如何避免未来数据泄露（Look-Ahead Bias）。

---

## 1. 核心概念

### 1.1 问题定义

多周期策略（Multi-Timeframe, MTF）中，小周期和大周期的K线收盘时间不同步。K线的时间戳代表**开盘时间**，收盘时间 = 开盘时间 + 周期长度。

例如：1h K线 `7:00` 的实际区间是 `[7:00, 8:00)`，要到 **8:00 才收盘**。

因此，当 5m K线走到 `7:05` 时，1h `7:00` 这根K线还在形成中，它的 OHLCV 和指标值是未确定的。此时最新已收盘的 1h K线是 `6:00`。如果在 5m `7:05` 这个时间点使用了 1h `7:00` 的最终收盘数据，就构成**未来数据泄露**（Look-Ahead Bias）——这是不可能在实盘中获得的信息。

### 1.2 正确行为

| 当前小周期时间 | 应该使用的大周期数据 | 原因 |
|:---:|:---:|:---|
| 5m 7:00 | 1h **6:00** | 7:00 的 1h K线刚开盘，最后一根已收盘的是 6:00 |
| 5m 7:05 | 1h **6:00** | 同上 |
| 5m 7:55 | 1h **6:00** | 同上，7:00 的 1h K线仍未收盘 |
| 5m 8:00 | 1h **7:00** | 7:00 的 1h K线已在 8:00 收盘 |

---

## 2. 时间映射机制（Mapping）

### 2.1 Backward Asof 语义

`build_backward_mapping(base_times, src_times)` 为 base 的每个时间点 `t`，找到 src 中 `<= t` 的最后一个索引。

```rust
// data_ops/mod.rs
fn build_backward_mapping(base_times: &[i64], src_times: &[i64]) -> Vec<Option<u32>> {
    for &t in base_times {
        while j + 1 < src_times.len() && src_times[j + 1] <= t {
            j += 1;
        }
        if src_times[j] <= t {
            out.push(Some(j as u32));
        }
    }
}
```

**映射结果示例**（base=5m, src=1h）：

| base 行 (5m) | base 时间 | mapping → src 索引 | src 时间 (1h) |
|:---:|:---:|:---:|:---:|
| 0 | 7:00 | 1 | 7:00 |
| 1 | 7:05 | 1 | 7:00 |
| 2 | 7:10 | 1 | 7:00 |
| ... | ... | 1 | 7:00 |
| 12 | 8:00 | 2 | 8:00 |

### 2.2 Mapping 不做偏移

> [!IMPORTANT]
> **Mapping 保持纯粹的时间对齐语义：`5m 7:05 → 1h 7:00`，不在 mapping 中做任何偏移处理。**
>
> 原因：Mapping 是多个模块共享的基础设施，如果在 mapping 中做偏移，会导致行为变得隐式，影响可读性和可维护性。未来数据泄露的防护在**消费端**（signal 模块）处理。

### 2.3 硬约束：base_data_key 必须是最小周期

> [!IMPORTANT]
> **`DataContainer.base_data_key` 必须对应所有 source 中的最小周期。**

**原因**：如果 base 不是最小周期（例如 base=1h 但存在 5m source），则会在后续计算中引入更细粒度 source，破坏统一时序基准。

**校验规则（最终版）**：采用“字符串周期 + time 最小正间隔”双校验，要求：

- source 命名必须符合 `数据名_周期名`（如 `ohlcv_5m`）
- 周期字符串需可解析为毫秒值（当前支持 `ms/s/m/h/d/w/M/y`）
- 工程约定：`M=28d`（下限校验），`y=364d`（下限校验），用于避免自然月/自然年的变长歧义
- `time` 列必须非递减（允许相同时间戳，禁止倒序）
- `time` 最小正间隔（跳过 `diff=0`）必须满足：`min_positive_interval >= declared_interval`
- 若 `min_positive_interval > declared_interval`，允许通过（可能由节假日/停盘导致）
- 每个 source 的 `time` 列至少需要 2 行；不足时直接报错
- `base_data_key` 的**声明周期**必须是所有 source 声明周期中的最小值
- 若 source 命名不符合 `数据名_周期名`（例如自定义键 `test_data`），则跳过该 source 的周期校验
- `base_data_key` 必须命名规范（可解析周期），否则直接报错

**双重校验位置**：

1. `build_time_mapping`：数据进入 mapping 基础设施时校验一次
2. 回测引擎入口（`run_backtest_engine` / `run_single_backtest`）：执行前再校验一次（防止调用方绕过 mapping 构建）

### 2.4 Mapping Null 值语义

当 `build_backward_mapping` 中 base 的某个时间点 `t` 早于所有 src 时间戳时，mapping 返回 `None`（即 null）。

**Null 传播链**：

```
build_backward_mapping 返回 None
    → take(indices) 对 null 索引产出 null 值
    → condition_evaluator 的 is_null() 检测到 null
    → has_leading_nan = true（该行被标记为无效）
    → 信号抑制（entry/exit 被强制为 false）
```

**设计原则**：使用 null（而非 NaN）表示映射缺失。null 的语义是"此行在 source 时间轴上无对应数据"，与"指标计算产生的 NaN"（如 RSI 前 N 行）有本质区别，但两者在信号抑制层面使用相同的安全机制处理。

**代码位置**：

- `data_ops/mod.rs:build_backward_mapping` — null 的产生
- `signal_generator/condition_evaluator/comparison_eval.rs:27` — `is_null()` 的捕获
- `signal_generator/mod.rs:74` — `has_leading_nan` 掩码的合并

### 2.5 Predecessor 保留逻辑

`align_sources_to_base_time_range`（`data_ops/mod.rs:105-153`）在对齐 source 到 base 时间范围时，会额外保留 `base_start` 之前最后一根 source bar（predecessor）。

**保留原因**：backward asof mapping 需要在 base 起始位置找到 `<= base_start` 的 source 数据。如果不保留 predecessor，base 的前几行可能映射为 null，导致不必要的信号抑制。

**安全性分析**：

- Predecessor 是**过去数据**（时间戳 `< base_start`），无 look-ahead bias
- Predecessor 的 OHLCV 和指标值在 base 开始前已经完全确定
- 即使 predecessor 的大周期 K 线刚好跨越 base_start，offset+1 机制仍然会在信号消费端正确处理

**无 predecessor 时**：mapping 为 null，由 §2.4 的 null 传播链安全处理。

---

## 3. 各模块的未来数据防护

### 3.1 Signal 生成模块

**文件**：`src/backtest_engine/signal_generator/operand_resolver.rs`

**✅ 已修复**：大周期数据 offset+1 补偿已实现，防止使用未收盘的大周期 K 线数据。

**修复实现**：在 `resolve_data_operand` 中，对需要 mapping 的 source（非自然映射），offset 额外 +1：

```rust
// 判断是否需要大周期偏移补偿
let needs_lookback_shift = !is_natural_mapping_for_source(processed_data, source_key)?;

for offset in offsets {
    let effective_offset = if needs_lookback_shift {
        offset + 1  // 大周期：多偏移一位，使用完全收盘的数据
    } else {
        offset       // 最小周期（自然映射）：保持不变
    };
    let shifted_series = series.shift(effective_offset);
    let mapped_series = apply_mapping_if_needed(&shifted_series, source_key, processed_data)?;
    result_series.push(mapped_series);
}
```

**效果**：

| 用户写法 | 实际取值 |
|:---|:---|
| `rsi, ohlcv_1h, 0` | 1h 上一行（已收盘） ✅ |
| `rsi, ohlcv_1h, 1` | 1h 上上行（已收盘） ✅ |
| `close, ohlcv_5m, 0` | 5m 当前行（不变） ✅ |

**判定标准**：`is_natural_mapping_for_source()` 返回 `false` 表示该 source 需要 asof mapping，因此需要偏移补偿；返回 `true` 表示 mapping 为 `0..n-1` 自然序列，无需补偿。

**对用户透明**：信号模板写法不变。用户仍然写 `rsi, ohlcv_1h, 0`，系统内部自动补偿，用户无感知。

**对 offset 模板语法的影响**：

- 用户的 offset 模板语法不变（`0/1/2` 写法不变）
- 非自然映射 source 的实际读取会整体后移 1 根（`offset=0` 读取最新已收盘）
- 同一 source 内部的相对偏移关系保持不变
- 跨 source 比较（如 15m vs 1h）结果可能变化，这正是修复掉未来数据泄露后的预期变化

### 3.2 Backtester 回测执行模块

**文件**：`src/backtest_engine/backtester/state/position_calculator.rs`

**状态**：✅ 无问题

回测器统一使用 **next-bar 模式**：用 `prev_bar` 的信号在 `current_bar` 的开盘价执行。

```rust
// 进场：prev_bar 信号 + current_bar 开盘价
if self.can_entry_long() && self.prev_bar.entry_long {
    self.action.entry_long_price = Some(self.current_bar.open);
}

// 离场（策略信号）：prev_bar 信号 + current_bar 开盘价
if self.has_long_position()
    && (self.prev_bar.exit_long || self.risk_state.should_exit_next_bar_long())
{
    self.action.exit_long_price = Some(self.current_bar.open);
}
```

**Risk 离场（In-Bar 模式）**：使用 `current_bar.high/low` 判断是否触及止损/止盈价格。这是当下状态机行为（价格已确定），不涉及未来数据。

### 3.3 Capital 资金结算模块

**文件**：`src/backtest_engine/backtester/state/capital_calculator.rs`

**状态**：✅ 无问题

完全是当下状态机：
- 使用 `current_bar.close` 计算未实现盈亏
- 使用已确定的 `entry_*_price` / `exit_*_price` 计算已实现盈亏
- balance、equity、fee 逐 bar 递推

不涉及未来数据。

### 3.4 Trading Bot 交易机器人

**文件**：`py_entry/trading_bot/_bot_process.py`

**状态**：✅ 无问题

#### 为什么 Bot 不需要去掉最后一根（未收盘）K线

Bot 在新周期起点触发（`is_new_period()`，周期开始后 5 秒内），从交易所拉取 OHLCV 数据，最后一根K线是刚开始的未收盘K线。

**保留最后一根未收盘K线是正确的**，原因：

1. **Backtester next-bar 模式**已经内置了一个周期的延迟。`parse_signal(df, -1)` 读到的最后一行 action，实际上是基于**倒数第二行**（已收盘K线）的 signal 生成的。

2. **entry_price 使用 `current_bar.open`**（最后一行的开盘价），在实盘中对应当前市场价。

3. **未收盘K线自身的 signal 永远不会被消费**——没有后续 bar 来读取它的 `prev_bar`。

#### 如果去掉最后一根K线，反而会出错

```
保留（正确）：  parse_signal(df, -1) = 最后行 action = 基于倒数第二行 signal ✅
去掉（错误）：  parse_signal(df, -1) = 倒数第二行 action = 基于倒数第三行 signal ❌（多延迟一个周期）
```

#### 安全保障

| 保障层 | 机制 | 说明 |
|--------|------|------|
| **`is_new_period()`** | 在周期起点后 5 秒内触发 | 保证最后一根K线刚开始，open 是有效的当前价格 |
| **Backtester next-bar** | action 基于 `prev_bar` signal | 未收盘K线的信号永远不被消费 |
| **signal 模块偏移修复** | 大周期 offset +1 | 多周期漏洞在回测引擎内部解决，Bot 无需关心 |

### 3.5 Indicator 计算模块

**文件**：`src/backtest_engine/indicators/mod.rs:58-77`

**状态**：✅ 无问题

Indicator 计算在 source **自身的时间轴**上执行，不使用 mapping 或 offset+1：

```rust
pub fn calculate_indicators(
    processed_data: &DataContainer,
    indicators_params: &IndicatorsParams,
) -> Result<IndicatorResults, QuantError> {
    for (source_name, mtf_indicator_params) in indicators_params.iter() {
        let source_data = processed_data.source.get(source_name.as_str())?;
        // 中文注释：直接在 source 自身 DataFrame 上计算，不涉及 mapping。
        let indicators_df = calculate_single_period_indicators(source_data, mtf_indicator_params)?;
        all_indicators.insert(source_name.clone(), indicators_df);
    }
}
```

**为什么这是正确的**：mapping 和 offset+1 的职责在**信号消费端**（`operand_resolver.rs`）。Indicator 模块只负责在各 source 自身时间轴上计算技术指标（RSI、EMA 等），产出结果存储在 `IndicatorResults` 的对应 source_key 下。当 signal 模块需要读取某个 source 的指标值时，才通过 mapping + offset+1 完成时间对齐和泄露防护。

### 3.6 Chart Display

**文件**：`py_entry/charts/_generation_panels.py`

**状态**：✅ 无问题

Chart 模块读取原始 indicator 值用于**可视化展示**，不参与信号决策或回测执行：

- 读取 `result.indicators[key]` 的列名和数据用于构建图表系列配置
- 读取 `data_dict.source[key]` 的 OHLCV 数据用于 K 线图和成交量图
- 输出为 `SeriesItemConfig` 配置对象，交由前端渲染

**无 look-ahead bias 风险**：Chart 纯粹是回测完成后的结果展示，不影响任何交易决策。

### 3.7 dataframe_utils

**文件**：`py_entry/io/dataframe_utils.py`

**状态**：✅ 无问题

`add_contextual_columns_to_dataframes` 只为 DataFrame 添加 `index`、`time`、`date` 等元数据列：

- `index`：行号（`with_row_index`）
- `time`：从对应 source 的 time 列 join 而来
- `date`：将 time 列格式化为 ISO 日期字符串

**不修改**指标值或信号值，纯粹的展示辅助。无 look-ahead bias 风险。

### 3.8 WF 边界注入与 offset+1 交互

**文件**：`src/backtest_engine/walk_forward/runner.rs:459-531`

**状态**：✅ 无问题

`build_injected_signals_for_window` 操作的是已经过完整信号生成流程（含 offset+1 处理）后的布尔信号列（`entry_long`、`exit_long`、`entry_short`、`exit_short`）。

**注入行为**：

1. 过渡期进场钳制：`transition` 段 entry 信号全部清零
2. 边界离场注入：在 transition 和 test 末尾各注入全平信号
3. 跨边界持仓处理：检测 transition 末尾是否有未平仓，若有则在 **transition 最后一 bar** 写入同向进场信号（`entry_long[transition_last_idx]` 或 `entry_short[transition_last_idx]`）；由于 next-bar 模式，该信号在 **test 第一根 bar 的开盘价**执行

**安全性**：注入只覆写布尔信号值，不重新读取 source 数据，不涉及 mapping 或 offset 操作。offset+1 的效果已固化在第一次评估产出的信号中。

### 3.9 Stitched 单调性验证

**文件**：`src/backtest_engine/walk_forward/runner.rs:394-431`

**状态**：✅ 已实现校验

当前校验体系：

| 校验项 | 函数 | 约束 | 目标 |
|--------|------|------|------|
| base 时间 | `assert_time_strictly_increasing` | 严格递增 | 确保 base bar 无重叠无回退 |
| 非 base source 时间 | `assert_source_times_non_decreasing` | 非递减（允许相等） | 大周期同 bar 映射到多 base 行时允许相同时间 |

**非递减而非严格递增的原因**：大周期 source 通过 mapping 展开后，同一根大周期 bar 对应的多根 base bar 会共享相同的 source 时间戳，因此只要求非递减。

---

## 4. 数据完整性保障总览

```
                    数据流
                    ────

  OHLCV 数据 (多周期)
       │
       ▼
  ┌─────────────────────────────┐
  │  build_time_mapping         │  ← 硬约束：base 必须是最小周期
  │  (backward asof mapping)    │    mapping 本身不做偏移
  └─────────────────────────────┘
       │
       ├──────────────────────────────────────┐
       ▼                                      ▼
  ┌─────────────────────────────┐   ┌──────────────────────────────┐
  │  Indicator Calculator       │   │  Chart Display               │
  │  (indicators/mod.rs)        │   │  (_generation_panels.py)     │
  │  在 source 自身时间轴计算   │   │  只读取结果用于可视化        │
  │  不使用 mapping/offset+1    │   │  不参与信号决策              │
  └─────────────────────────────┘   └──────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────┐
  │  Signal Generator           │  ← 大周期 offset +1（已修复 ✅）
  │  (resolve_data_operand)     │    最小周期不偏移
  │                             │    用户写法不变
  └─────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────┐
  │  Backtester                 │  ← next-bar 模式（天然延迟一个周期）
  │  (position_calculator)      │    进场/离场用 prev_bar signal
  │                             │    价格用 current_bar.open
  └─────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────┐
  │  Capital Calculator         │  ← 当下状态机
  │  (capital_calculator)       │    只用已确定的价格
  └─────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────┐
  │  Trading Bot                │  ← parse_signal(df, -1) 读 next-bar 产物
  │  (parse_signal / executor)  │    保留未收盘K线
  │                             │    不需要也不应该去掉最后一根
  └─────────────────────────────┘
```

---

## 5. 已修复项

| 模块 | 文件 | 问题 | 修复方案 | 状态 |
|------|------|------|---------|------|
| **Signal** | `operand_resolver.rs` | 大周期数据未偏移，使用了未收盘K线 | 非自然映射 source offset +1 | ✅ 已修复 |
| **data_ops + top_level_api** | `data_ops/mod.rs` / `top_level_api.rs` | 缺少 base 必须是最小周期的硬约束 | 采用"最小时间间隔"规则，在 mapping 与引擎入口双重校验 | ✅ 已修复 |

---

## 6. 测试联动说明

Signal 修复后，测试侧手写对照逻辑必须同步：

- 对非自然映射 source，手写计算也必须先 `shift(1)` 再映射
- 否则会出现"引擎已修复、手写基线仍泄露"导致的整体错位失败

---

## 7. 更新日志

### v1.1.0 (2026-02-22)

- **A1**: 标记 Signal offset+1 bug 为"已修复"，更新 §3.1 和 §5。
- **A2**: 新增 §2.4 Mapping Null 值语义，说明 null 传播链和信号抑制机制。
- **A3**: 新增 §2.5 Predecessor 保留逻辑，说明 `align_sources_to_base_time_range` 的设计意图。
- **A4**: 新增 §3.5 Indicator 计算模块分析，确认在 source 自身时间轴计算、不涉及 mapping。
- **A5**: 新增 §3.6 Chart Display 分析，确认纯可视化展示、无 look-ahead bias。
- **A6**: 新增 §3.7 dataframe_utils 分析，确认只添加元数据列、不修改指标/信号。
- **A7**: 新增 §3.8 WF 边界注入与 offset+1 交互分析，确认注入操作安全。
- **A8**: 新增 §3.9 Stitched 单调性验证，记录 base 严格递增 + source 非递减校验。
- **A9**: 新增 §8 WF Warmup 风险分析，记录 transition_bars 不足导致指标 NaN 的风险和应对方案。
- **A10**: 更新 §4 数据流图，加入 Indicator Calculator 和 Chart Display 节点。
- **B1**: 新增 rebase 越界校验（`data_ops/mod.rs`）。
- **B2**: 新增 all-None mapping 注释（`data_ops/mod.rs`）。
- **B3**: 新增 stitched 多周期 source 时间非递减校验（`runner.rs`）。

### v1.0.0 (2026-02-21)
- 初始版本：梳理多周期数据映射机制和未来数据泄露防护策略。
- 确认 Signal 模块大周期偏移 Bug 及修复方案。
- 确认 Backtester、Capital、Bot 模块无问题。
- 明确 base_data_key 必须是最小周期的硬约束。

---

## 8. WF Warmup 风险分析（设计文档）

> [!WARNING]
> 本节为设计文档，记录已知风险和候选方案，暂不实现。后续独立 PR 处理。

### 8.1 问题描述

Walk-Forward 测试中，每个窗口的 `transition_bars` 用于预热指标和建立持仓状态。当高周期指标（如 4h RSI(14)）需要大量历史数据预热时，`transition_bars` 可能不足，导致 test 窗口开始时指标仍为 NaN，进而产生不必要的信号抑制。

### 8.2 具体示例

```
base = 5m, source = 4h
RSI(14) 需要 14 根 4h K 线预热
14 根 4h = 14 × 48 根 5m = 672 根 base bars

若 transition_bars = 200，则预热数据严重不足：
- RSI 前 672 行均为 NaN
- test 窗口开始时 RSI 仍为 NaN
- has_leading_nan = true → 信号被抑制
- 实际可用数据大幅缩减
```

### 8.3 has_leading_nan 机制

`has_leading_nan` 是系统检测指标预热状态的核心机制。

**语义定义**：`has_leading_nan[i] = true` 表示在第 `i` 行，**任意**信号字段（`entry_long` / `exit_long` / `entry_short` / `exit_short`）的至少一个操作数存在 NaN 或 null。是所有信号条件的 NaN 掩码的**并集**（bitor 合并），而非单独字段的独立掩码。

| 阶段 | 位置 | 行为 |
|------|------|------|
| **创建** | `signal_generator/mod.rs:74` | 初始化为全 false 的布尔掩码 |
| **检测** | `condition_evaluator/comparison_eval.rs:27` | `is_nan() \| is_null()` 检测无效值 |
| **合并** | `signal_generator/mod.rs:41` | 四个信号字段的 NaN 掩码全部 bitor 累积 |
| **进场抑制** | `backtester/signal_preprocessor.rs`（规则6） | `has_leading_nan=true` 时强制 entry_long/entry_short 为 false |
| **计数** | `performance_analyzer/mod.rs:22` | 统计 `has_leading_nan` 为 true 的行数 |

**backtester 保守策略（规则6）**：

`has_leading_nan=true` 可能意味着 exit 信号的操作数也有 NaN——此时 exit 在 NaN 期内被 `condition_evaluator` 强制抑制为 false，进场后无法按策略正常离场（只能靠止损止盈或 WF 强制离场）。因此 `signal_preprocessor` 在预处理阶段将 `has_leading_nan=true` 的行的 entry 全部清零，防止在出口不明确的情况下开仓。exit 信号**不受**本规则影响，由 `condition_evaluator` 内部的 NaN 检测自行处理。

**exit NaN 期被迫延长持仓**：

- **普通回测**：规则6（`signal_preprocessor.rs`）已阻止在 `has_leading_nan=true` 期间开仓，因此不会出现"进了场但无法按策略离场"的情况。此风险在普通回测中已消除。
- **WF 跨边界持仓**：跨边界持仓由 WF 注入机制（`build_injected_signals_for_window`）强制进入，不受规则6约束。若 transition 预热不足导致 test 期间仍有 NaN，exit 信号在 NaN 行会被抑制为 false，被迫延长持仓至 NaN 消散或窗口末强制离场。**根本解法：保证 `transition_bars` ≥ 最大指标预热期（参考 §8.5 公式），使 NaN 在 test 段开始前完全消散。**

**has_leading_nan_count 的含义**：

统计的是"任意信号字段有 NaN"的行数，包含所有 exit 条件的预热期，精确反映了"在此之前开仓是不安全的"行数范围。

**边界问题：negated 条件在 NaN 期的误触发（已修复）**

存在一个 negated 条件与 NaN 的交互 bug：

```
RSI = NaN
→ perform_comparison: result = false（mask 强制）
→ condition.negated = true: !false = true  ← NaN 行误变为 true
→ exit 信号在 NaN 期意外触发 true
```

对 entry 条件：规则6（`signal_preprocessor.rs`）会将 `has_leading_nan=true` 的行的 entry 清零，有兜底。

对 exit 条件：exit 不受规则6保护，若当前有持仓（如 WF 跨边界持仓）且 exit 使用了 negated 条件，可能在 NaN 期误触发离场。

**修复**（`condition_evaluator/mod.rs`）：在 negation 之后重新应用 `result & !mask`，保证 NaN 行无论取反与否始终为 false。该操作幂等（`(x & !m) & !m = x & !m`），对非 negated 场景无副作用。

### 8.4 候选方案

#### 方案 1：从训练数据尾部借数据扩展 transition

**思路**：自动检测最大预热需求，从训练窗口尾部额外借用数据扩展 transition 段。

**优点**：
- 适用于常见指标（RSI、EMA、MACD 等），自动化程度高
- 不浪费 test 数据
- transition 段不开仓（进场被钳制），借用的训练数据仅用于指标预计算

**风险讨论**：
- ❌ 不会造成训练数据污染：过渡期内进场信号被钳制（`entry = false`），借用的训练数据不会影响 test 段的交易决策
- ⚠️ 理论风险（实践中无已知严重影响）：任何连续回测的 test 段指标值天然都基于历史数据（含训练数据）计算，方案 1 与此一致；滚动窗口指标（RSI、EMA、MACD 等）在滚满窗口后完全遗忘初始状态，无影响；状态依赖型指标（如 PSAR）的初始状态理论上受借用数据影响，但实践中尚无已知案例造成显著偏差。以防万一，使用方案 1 时应与方案 2 对比验证结果一致性

#### 方案 2：直接增大 transition_bars

**思路**：用户手动设置足够大的 `transition_bars`。

**优点**：
- 绝对安全，无数据交叉风险
- 实现简单

**缺点**：
- 浪费 test 数据，减少可用回测区间
- 需要用户手动计算最小预热需求

### 8.5 最小 transition_bars 推荐公式

```
min_transition_bars = max(
    base_indicator_warmup,
    max_source_warmup_in_base_bars
)

其中：
  max_source_warmup_in_base_bars = max(
      indicator_period × (source_interval / base_interval)
      for each non-base source
  )

例：
  base=5m, source=4h, RSI(14):
  min = 14 × (240 / 5) = 14 × 48 = 672 base bars
```

### 8.6 决策

暂不实现自动预热扩展。当前策略：

1. 依赖 `has_leading_nan` 机制自动检测和抑制不可靠信号
2. 用户在配置 WF 时参考 §8.5 公式设置合理的 `transition_bars`
3. 后续独立 PR 评估方案 1 的实现可行性
