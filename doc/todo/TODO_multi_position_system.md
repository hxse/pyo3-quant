# TODO: 多仓位系统设计方案 (Multi-Position System)

本文档描述多仓位回测系统的完整设计。该系统**直接替代**现有的单仓位系统。

---

## 1. 核心概念：一个仓位 + 条件单

### 1.1 仓位模型

**始终只有一个仓位。** 不存在"多个独立子仓位"的概念。

```
Position = {
    direction: Long / Short
    total_units: f64           // 当前总大小（加仓增大，减仓减小）
    base_entry_price: f64      // 底仓入场价（锚点，不随加减仓变化）
}
```

- 加仓 = `total_units` 增大
- 减仓 = `total_units` 减小
- 全平 = `total_units` 归零，仓位生命周期（交易组）结束

### 1.2 条件单 (Conditional Orders)

**所有的 SL、TP、TSL、ReduceLayer 本质上都是同一个东西：一张"待触发的减仓单"。**

| 来源 | 触发锚点 | 触发条件 | 动作 |
|------|---------|---------|------|
| AddLayer 的 SL | 该次加仓的成交价 | 跌 X% | 减仓 N units |
| AddLayer 的 TP | 该次加仓的成交价 | 涨 X% | 减仓 N units |
| AddLayer 的 TSL | 该次加仓后的最高/最低价 | 回撤 X% | 减仓 N units |
| ReduceLayer | 底仓入场价 | 涨/跌 X% | 减仓 N units |

> **条件单跟交易所的挂单系统 1:1 对应。** SL/TP = Stop/Limit Order，TSL = Trailing Stop Order。交易机器人可以直接映射为交易所挂单。

### 1.3 条件单作废规则

当一个条件单对应的 units 已被其他方式消耗（例如 ReduceLayer 先触发了），该条件单自动作废。

### 1.4 TSL 特殊性

TSL 不是固定触发价的条件单，它的触发价是**动态的**（跟踪最高/最低价）。回测中需要逐 bar 更新触发价，与现有 TSL 逻辑一致。

---

## 2. 退出层级与铁律

### 2.1 底仓是锚

> **底仓 (Base Position) 是所有网格层的锚。底仓离场 = 整个交易组生命周期结束。**

| 触发者 | 影响范围 |
|--------|---------|
| 底仓 SL/TP/TSL 触发 | **全灭**：取消所有条件单，清空仓位 |
| Exit 信号 | **全灭**：取消所有条件单，清空仓位 |
| 交易组总止损 | **全灭**：取消所有条件单，清空仓位 |
| Force_Close | **全灭**：取消所有条件单，清空仓位 |
| AddLayer 的 SL/TP/TSL 触发 | **仅减对应 units**：其他不受影响 |
| ReduceLayer 触发 | **仅减指定 units**：按比例从所有贡献中扣减 |

### 2.2 交易组总止损 (Group Stop Loss)

**总止损不是价格条件，是账本条件。**

```
group_total_pnl = 累计已实现盈亏 + 当前剩余仓位浮盈

if group_total_pnl < group_stop_loss_threshold:
    全平
```

> 场景：趋势加仓后价格回撤，多个加仓层的 SL 连续触发，虽然价格没跌穿底仓入场价，但过程中的累计亏损 + 剩余浮亏已超过阈值。

---

## 3. 输入参数

### 3.1 BacktestParams 扩展

```rust
struct BacktestParams {
    // ===== 现有参数 =====
    initial_capital: f64,
    fee_fixed: f64,
    fee_pct: f64,
    sl_pct: Option<Param>,
    tp_pct: Option<Param>,
    tsl_pct: Option<Param>,
    // ... 其余风控参数 ...

    // ===== 多仓位参数 =====
    add_layers: Vec<AddLayer>,          // 加仓配置（空 = 无加仓）
    reduce_layers: Vec<ReduceLayer>,    // 减仓配置（空 = 无减仓）
    group_stop_loss_pct: Option<f64>,   // 交易组总止损阈值
    enable_chart_data: bool,            // 是否输出 Chart DF
}
```

### 3.2 AddLayer（加仓层）

```rust
struct AddLayer {
    trigger_pnl_pct: f64,       // 触发条件（相对底仓入场价的价格偏离百分比）
                                // 负数 = 逢低加仓（Grid/DCA），正数 = 趋势加仓（Pyramiding）
    units: f64,                 // 加多少（底仓大小的倍数，如 1.0 = 加一个底仓）
    leverage: f64,              // 本次加仓使用的杠杆

    // 独立风控（全部 Optional，None = 继承 BacktestParams 的全局配置）
    sl_pct: Option<f64>,        // 本层止损（触发后减仓 units 单位）
    tp_pct: Option<f64>,        // 本层止盈
    tsl_pct: Option<f64>,       // 本层追踪止损
}
```

### 3.3 ReduceLayer（减仓层）

```rust
struct ReduceLayer {
    trigger_pnl_pct: f64,       // 触发条件（相对底仓入场价的价格偏离百分比）
    units: f64,                 // 减多少（底仓大小的倍数）
}
```

### 3.4 触发锚点统一规则

所有 AddLayer 和 ReduceLayer 的 `trigger_pnl_pct` **统一以底仓入场价 (base_entry_price) 为锚**：

```
trigger_condition = (current_price / base_entry_price) - 1.0

AddLayer trigger = -0.10  → 价格跌到底仓入场价的 90% 时触发
ReduceLayer trigger = +0.05 → 价格涨到底仓入场价的 105% 时触发
```

### 3.5 参数校验

```
对于每个 AddLayer[i]:
  计算 trigger 对应的触发价格
  计算 base SL 对应的止损价格
  如果触发价格在止损价格**之外**（即底仓会先被止损，加仓永远不会触发）:
    → ERROR: "AddLayer[{i}] trigger 不可达，底仓 SL 会先触发全灭"
```

### 3.6 破坏性更新：多仓位系统直接替代单仓位系统

**不搞兼容层。** 多仓位系统是单仓位系统的超集，直接替代：
- `add_layers` 和 `reduce_layers` 类型为 `Vec<...>`（非 `Option`），空数组 = 单仓位行为
- 逻辑完全复用，无任何 `if 单仓位 then X else Y` 的分支
- 输出格式（Bar DF + Trade DF + Chart DF）始终一致
- 原有单仓位回测系统**废弃**

---

## 4. 输出：三 DF 架构 (Triple DataFrame)

### 设计原则

| DF | 粒度 | 受众 | 核心问题 |
|----|------|------|---------|
| **Bar DF** | 一行一根 K 线 | 策略引擎 / 交易机器人 | "我现在有多少钱？仓位状态？" |
| **Trade DF** | 一行一个事件 | 绩效分析 / 风控审计 | "每次操作做了什么？赚了还是亏了？" |
| **Chart DF** | 一行一根 K 线 × N 条件单 | 可视化 / 调试 | "画线需要什么坐标？" |

- Bar DF 和 Trade DF **始终输出**
- Chart DF **可选输出**（回测参数中配置 `enable_chart_data=true`，引擎内部生成并返回）

### 4.1 Bar DF

> 只包含账户级聚合信息。仓位价格和风控线分别由 Trade DF 和 Chart DF 承载。

#### 资金状态（不变）

| 列名 | 类型 | 说明 |
|------|------|------|
| `balance` | f64 | 已实现余额（仅在**交易组全平时**更新） |
| `equity` | f64 | 含浮盈净值（每 bar 更新） |
| `current_drawdown` | f64 | 当前回撤比例 |
| `trade_pnl_pct` | f64 | 本 bar **交易组结束时**的总 PnL（中间减仓不结算到此列，只累积到 group_realized_pnl） |
| `total_return_pct` | f64 | 累计收益率 |
| `fee` | f64 | 本 bar 手续费 |
| `fee_cum` | f64 | 累计手续费 |

#### 仓位状态

| 列名 | 类型 | 说明 |
|------|------|------|
| `total_units` | f64 | 当前仓位大小（0=空仓，以**底仓大小**为 1.0 的倍数） |
| `position_direction` | i8 | 0=空仓, 1=多, -1=空 |

#### 交易组损益

| 列名 | 类型 | 说明 |
|------|------|------|
| `group_id` | i32 | 当前交易组 ID（0=空仓） |
| `group_realized_pnl` | f64 | 本组累计已实现盈亏 |
| `group_unrealized_pnl` | f64 | 本组当前浮盈 |
| `group_total_pnl` | f64 | = realized + unrealized（用于总止损判断） |

#### 状态机（不变）

| 列名 | 类型 | 说明 |
|------|------|------|
| `frame_state` | u8 | 17 种白名单状态（基于聚合字段推断） |
| `first_entry_side` | i8 | 进场标记（同现有语义） |
| `in_bar_direction` | i8 | 风控离场标记（同现有语义） |
| `has_leading_nan` | bool | 透传 |

#### 列职责分工

- 仓位入场/离场价格 → Trade DF（事件日志中记录）
- 风控价格线 (SL/TP/TSL 轨迹) → Chart DF（可选输出）
- ATR 值 → Chart DF（可选输出）

### 4.2 Trade DF（事件日志）

> 一行一个事件。每次开仓、加仓、减仓、全平都是一行。

| 列名 | 类型 | 说明 |
|------|------|------|
| `group_id` | i32 | 属于哪个交易组 |
| `event_id` | i32 | 事件序号（组内递增，**严格保证回测与实盘执行顺序一致**） |
| `bar_index` | i32 | 发生在哪根 K 线 |
| `event_type` | i8 | 1=开仓, 2=加仓, -1=减仓, 0=全平 |
| `trigger_source` | i8 | 触发来源（见下表） |
| `price` | f64 | 成交价 |
| `units_delta` | f64 | 变动量（正=加, 负=减） |
| `leverage` | f64 | 本次事件的杠杆（减仓时 NaN） |
| `realized_pnl` | f64 | 本次事件的已实现 PnL（加仓时 NaN） |
| `fee` | f64 | 本次事件的手续费 |
| `total_units_after` | f64 | 事件后的仓位大小 |
| `group_realized_pnl_after` | f64 | 事件后的组累计已实现 PnL |

**trigger_source 枚举**：

| 值 | 含义 |
|:--:|------|
| 0 | Signal（策略信号） |
| 1 | AddLayer |
| 2 | ReduceLayer |
| 3 | SL 条件单 |
| 4 | TP 条件单 |
| 5 | TSL 条件单 |
| 6 | 交易组总止损 (Group SL) |
| 7 | Force Close (资金耗尽等) |

### 4.3 Chart DF（按需生成）

> 追踪每张活跃条件单在每根 K 线上的触发价格。仅在需要可视化时生成。

| 列名 | 类型 | 说明 |
|------|------|------|
| `bar_index` | i32 | 映射到 Bar DF |
| `source_event_id` | i32 | 这张条件单由哪次加仓事件挂出的 |
| `order_type` | i8 | 1=SL, 2=TP, 3=TSL |
| `trigger_price` | f64 | 当前触发价（TSL 逐 bar 变化，SL/TP 固定） |
| `target_units` | f64 | 触发后减多少 units |
| `status` | i8 | 1=活跃, 0=已触发, -1=已作废 |

### 图表渲染映射

| 图表元素 | 数据来源 |
|---------|---------|
| K 线 (Candlestick) | 原始 OHLCV 输入 |
| 资金曲线 (Equity) | Bar DF `equity` |
| 回撤曲线 | Bar DF `current_drawdown` |
| 开仓/加仓箭头 | Trade DF `event_type > 0` 的 `bar_index` + `price` |
| 减仓/全平箭头 | Trade DF `event_type <= 0` 的 `bar_index` + `price` |
| SL/TP 水平线 | Chart DF `order_type=SL/TP, status=1` |
| TSL 曲线 | Chart DF `order_type=TSL` 按 `bar_index` 连线 |

---

## 5. PnL 算法：逐笔贡献追踪

### 5.1 内部数据结构

即使对外只展示"一个仓位"，内部必须记住每笔加仓的参数用于精确计算 PnL。

```rust
struct Contribution {
    event_id: i32,
    entry_price: f64,
    units: f64,          // 剩余 units（减仓时按比例减少）
    leverage: f64,
    margin: f64,         // 投入的保证金
}

struct GroupState {
    contributions: Vec<Contribution>,
    cumulative_realized_pnl: f64,
}
```

### 5.2 PnL 公式

**每笔贡献的浮盈**（名义盈亏）：

```
contribution_unrealized = units × (current_price - entry_price)
```

> 杠杆不影响名义盈亏，只影响保证金占用。

**交易组总 PnL**（每根 K 线计算）：

```
group_unrealized = Σ (每个活跃 contribution 的 unrealized)
group_total_pnl  = cumulative_realized_pnl + group_unrealized
```

### 5.3 三种减仓场景的结算

**条件单触发（SL/TP/TSL of 某次加仓）**：

条件单知道自己来自哪个 `event_id`，直接找到对应的 `Contribution`：

```
realized = contribution.units × (exit_price - contribution.entry_price)
从 contributions 中移除该条目
cumulative_realized_pnl += realized
```

**ReduceLayer 触发（通用减仓）**：

按比例从所有活跃 contribution 中扣减：

```
要减 X units
比例 = X / Σ contribution.units

for each contribution:
    减去 = contribution.units × 比例
    realized += 减去 × (exit_price - contribution.entry_price)
    contribution.units -= 减去
    contribution.margin 按比例减少

cumulative_realized_pnl += realized
```

**全平**：

```
for each contribution:
    realized += contribution.units × (exit_price - contribution.entry_price)
清空 contributions
```

---

## 6. 手续费

### 每次事件独立收费

```
fee_per_event = fee_fixed + abs(units_delta) × price × fee_pct
```

- 每个事件（开仓/加仓/减仓/全平）按此公式收一次费
- `fee_fixed` 每次事件收一次（悲观：事件越多费越高）
- `fee_pct` 基于实际成交价和成交量
- `realized_pnl` **不扣除手续费**，手续费独立记录（与现有设计一致）

---

## 7. 状态机兼容性

### 核心原则

> 加仓/减仓是 `hold_long` / `hold_short` 内部的**子事件**，不影响宏观 `FrameState` 推断。
> **资金结算 (Balance Update)** 仅在 **交易组全平 (Group Close)** 时统一更新。
> 中间的减仓事件产生的 `realized_pnl` 会累积在 `group_realized_pnl` 中。
> **净值 (Equity Update)** 则是**每根 K 线实时更新**的：`Equity = Balance(未动) + Group_Realized(中间减仓) + Group_Unrealized(剩余持仓)`。

### 推断输入字段

多仓位系统使用以下聚合字段推断 17 种状态（与现有白名单完全一致）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_units` | f64 | 当前仓位大小（0=空仓） |
| `position_direction` | i8 | 仓位方向 |
| `first_entry_side` | i8 | 进场标记（与现有完全一致） |
| `in_bar_direction` | i8 | In-Bar 风控离场标记（与现有完全一致） |

### 推断规则

| # | 推断条件 | 状态 |
|:-:|---------|------|
| 1 | units=0, 无事件 | `no_position` |
| 2 | units>0, dir=1, first_entry=0 | `hold_long` (延续) |
| 3 | units>0, dir=1, first_entry=1 | `hold_long_first` (首次进场) |
| 4 | units>0, dir=-1, first_entry=0 | `hold_short` (延续) |
| 5 | units>0, dir=-1, first_entry=-1 | `hold_short_first` (首次进场) |
| 6-8 | 多头离场（信号/风控/秒杀） | `exit_long_*` |
| 9-11 | 空头离场（信号/风控/秒杀） | `exit_short_*` |
| 12-15 | 反手 | `reversal_*` |
| 16 | 跳空保护 | `gap_blocked` |
| 17 | 资金耗尽 | `capital_exhausted` |

---

## 8. 策略场景验证

### 8.0 底仓进场规则

**底仓的进场/离场完全由现有的 `SignalTemplate` 信号系统驱动，与多仓位逻辑无关。**

信号系统生成 `entry_long`、`exit_long`、`entry_short`、`exit_short` 四个布尔信号列，经过信号清洗（R1-R5 规则）后，触发底仓的开仓和平仓。多仓位系统中的 `add_layers` / `reduce_layers` 只在底仓开仓后才开始工作。

```
完整执行流程：
  1. SignalTemplate 生成 entry/exit 信号 → 底仓开仓（event_type=1）
  2. 底仓存续期间，AddLayer/ReduceLayer 条件持续检测
  3. SignalTemplate 生成 exit 信号 → 全平（event_type=0）
```

---

### 8.1 布林带均值回归 + 逢低定投 (BBands Mean Reversion + DCA)

**策略思路**：价格跌破布林下轨时入场，认为是超跌，如果继续下跌则分批加仓摊平成本，价格回归中轨时离场。

```python
# ---- 指标 ----
indicators = {
    "ohlcv_15m": {"bbands": {"period": Param.create(20), "std": Param.create(2)}},
    "ohlcv_1h":  {"rsi": {"period": Param.create(14)}},
}

# ---- 信号 ----
signal_template = SignalTemplate(
    entry_long=SignalGroup(logic='AND', comparisons=[
        "close x< bbands_lower",         # 价格跌破布林下轨
        "rsi,ohlcv_1h, < 40",            # 1h RSI 超卖确认
    ]),
    exit_long=SignalGroup(logic='OR', comparisons=[
        "close x> bbands_middle",         # 价格回归中轨
        "rsi,ohlcv_1h, > 70",            # RSI 超买
    ]),
)

# ---- 回测参数 ----
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_pct=0.001,
    # 底仓风控：无 SL（保证锚点存活），无 TP（靠信号离场）
    # sl_pct / tp_pct / tsl_pct 均不设置
    add_layers=[
        AddLayer(trigger=-0.05, units=1.0, leverage=1.0),  # 跌5%加仓
        AddLayer(trigger=-0.10, units=1.0, leverage=1.0),  # 跌10%加仓
        AddLayer(trigger=-0.15, units=1.0, leverage=1.0),  # 跌15%加仓
    ],
    reduce_layers=[],
    group_stop_loss_pct=-0.25,  # 交易组总亏损超过25%全灭
)
```

**特点**：底仓无 SL 保证锚点存活，纯靠信号退出 + 总止损兜底。✅

---

### 8.2 趋势跟踪 + 金字塔加仓 (Trend Following + Pyramiding)

**策略思路**：多周期确认趋势后入场，趋势延续时逐步加仓放大利润，每层独立 TSL 保护利润，从外到内逐层剥落。

```python
# ---- 指标 ----
indicators = {
    "ohlcv_15m": {"bbands": {"period": Param.create(14), "std": Param.create(2)}},
    "ohlcv_1h":  {"rsi": {"period": Param.create(14)}},
    "ohlcv_4h":  {"sma_0": {"period": Param.create(8)}, "sma_1": {"period": Param.create(21)}},
}

# ---- 信号 ----
signal_template = SignalTemplate(
    entry_long=SignalGroup(logic='AND', comparisons=[
        "close > bbands_upper",             # 15m 突破布林上轨
        "rsi,ohlcv_1h, > 50",              # 1h RSI 多头区域
        "sma_0,ohlcv_4h, > sma_1,ohlcv_4h,",  # 4h 均线多头排列
    ]),
    exit_long=SignalGroup(logic='OR', comparisons=[
        "sma_0,ohlcv_4h, x< sma_1,ohlcv_4h,",  # 4h 均线死叉
    ]),
)

# ---- 回测参数 ----
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_pct=0.001,
    # 底仓风控：TSL 保护利润
    tsl_pct=Param.create(0.05),
    add_layers=[
        # trigger 为正数：越涨越买
        AddLayer(trigger=+0.05, units=0.5, leverage=1.0, tsl_pct=0.03),  # 涨5%加半仓
        AddLayer(trigger=+0.10, units=0.5, leverage=1.0, tsl_pct=0.03),  # 涨10%再加半仓
    ],
    reduce_layers=[],
)
```

**特点**：网格层 TSL(3%) 比底仓 TSL(5%) 更紧，趋势反转时加仓层先被剥落，底仓最后兜底。✅

---

### 8.3 震荡网格：低吸高抛 (Range Grid Trading)

**策略思路**：RSI 区间穿越识别震荡区间，在区间内分批低买高卖，加仓和减仓完全对称。

```python
# ---- 指标 ----
indicators = {
    "ohlcv_1h": {"rsi": {"period": Param.create(14)}},
}

# ---- 信号 ----
signal_template = SignalTemplate(
    entry_long=SignalGroup(logic='AND', comparisons=[
        "rsi,ohlcv_1h,0 x> 30..70",      # RSI 自下穿过 30 激活，(30,70) 区间持续
    ]),
    exit_long=SignalGroup(logic='OR', comparisons=[
        "rsi,ohlcv_1h, > 75",            # RSI 极度超买时离场
    ]),
)

# ---- 回测参数 ----
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_pct=0.001,
    # 底仓无 SL（震荡策略，扛得住回调）
    add_layers=[
        AddLayer(trigger=-0.03, units=1.0, leverage=1.0),  # 跌3%加仓
        AddLayer(trigger=-0.06, units=1.0, leverage=1.0),  # 跌6%加仓
        AddLayer(trigger=-0.09, units=1.0, leverage=1.0),  # 跌9%加仓
    ],
    reduce_layers=[
        ReduceLayer(trigger=+0.03, units=1.0),  # 涨3%减仓
        ReduceLayer(trigger=+0.06, units=1.0),  # 涨6%再减仓
        ReduceLayer(trigger=+0.09, units=1.0),  # 涨9%再减仓
    ],
    group_stop_loss_pct=-0.15,  # 总止损兜底
)
```

**特点**：加仓和减仓完全对称，对称网格在震荡市中反复收割价差。✅

---

### 8.4 突破 + 独立层止损 (Breakout + Per-Layer SL)

**策略思路**：突破入场后激进加仓，但每层加仓都设独立止损保护，假突破时快速减仓控损。

```python
# ---- 信号 ----
signal_template = SignalTemplate(
    entry_long=SignalGroup(logic='AND', comparisons=[
        "close x> bbands_upper",            # 布林上轨突破
        "volume > volume,, 1",              # 放量确认
    ]),
    exit_long=SignalGroup(logic='OR', comparisons=[
        "close x< bbands_middle",           # 回落中轨
    ]),
)

# ---- 回测参数 ----
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_pct=0.001,
    sl_pct=Param.create(0.03),              # 底仓 SL 3%
    add_layers=[
        AddLayer(trigger=+0.02, units=1.0, leverage=2.0, sl_pct=0.02),  # 涨2%加仓，2倍杠杆，独立SL 2%
        AddLayer(trigger=+0.04, units=0.5, leverage=2.0, sl_pct=0.015), # 涨4%加仓，更紧SL
    ],
    reduce_layers=[],
)
```

**特点**：加仓层使用高杠杆 + 紧止损，假突破时条件单快速止损减仓，真突破时利润放大。底仓 SL 3% > 加仓 trigger 2%，所以不会出现底仓先被杀的情况。✅

---

## 9. 实现范围评估

### 可直接复用的逻辑（约 60%）

| 模块 | 说明 |
|------|------|
| 信号预处理 (`signal_preprocessor.rs`) | 信号清洗规则 R1-R5 不变 |
| ATR 计算 (`atr_calculator.rs`) | 计算逻辑不变 |
| 风控价格公式 (`risk_price_calc.rs`) | SL/TP/TSL 公式不变，每个条件单复用 |
| 跳空保护 (`gap_check.rs`) | 底仓进场时的跳空检查不变 |
| 触发检测 (`trigger_checker.rs`) | 每个条件单复用现有触发检测逻辑 |

### 需要重写的部分

| 模块 | 内容 | 难度 |
|------|------|:----:|
| `BacktestState` | 引入 `GroupState` + `Contribution` 列表 | ⭐⭐⭐ |
| `CapitalCalculator` | 逐贡献结算 + 交易组总损益 + Equity 实时更新 | ⭐⭐⭐ |
| `RiskState` | 多条件单并行管理（每个 AddLayer 独立的 SL/TP/TSL） | ⭐⭐⭐ |
| `FrameState::infer()` | 基于聚合字段推断 | ⭐⭐ |
| `OutputBuffers` | 输出 Bar DF + Trade DF + Chart DF（可选） | ⭐⭐ |
| 绩效分析 | 基于 Trade DF 事件日志统计 | ⭐⭐ |

---

## 10. 当前状态：暂缓实现

> **本文档作为架构蓝图保留，暂不实现。**

### 10.1 暂缓理由

**1. 与当前交易哲学不匹配**

当前交易体系的核心是：`小资金 × 高杠杆 × 短生命周期策略 × Calmar → MaxSafeLeverage`。

- 高杠杆已经用 `SafetyFactor / MDD` 杠到极限，没有多余 margin 给加仓
- 加仓必然增大 MDD，反而降低安全杠杆倍数，与 Calmar 优先原则**自相矛盾**
- DCA/Grid/Pyramiding 本质上是**防守策略**，适合大资金、低杠杆、长周期持仓
- 15m/1h 级别的波段策略，持仓周期短，没有"逢低加仓"的时间窗口
- 详见 `doc/trading_philosophy/quantitative_trading.md`

**2. 无法做相关性验证**

当前单仓位系统的可信度建立在与 backtesting.py 的**相关性分析**之上（参见 `py_entry/Test/backtest/correlation_analysis/test_correlation.py`）。

多仓位系统面临的验证困境：
- backtesting.py **不支持多仓位**，无法作为对标引擎
- 没有第三方引擎可用于交叉验证
- 自己测自己 = 没有外部参照 = 无法确信引擎正确性
- 破坏性更新意味着废弃现有单仓位系统，如果新引擎有 bug，没有退路

**3. 当前没有强刚需场景**

- 趋势加仓/减仓：单仓位 + TSL 已经够用
- 震荡网格：单仓位均值回归策略也能覆盖
- 逢低定投：长线策略，手动交易可替代
- 套利策略（真正的需求）：本质是多资产协调，不是多仓位，用信号注入 + 多实例即可实现

### 10.2 未来启动的前提条件

1. **找到支持多仓位的第三方回测引擎**，用于做相关性分析验证
2. **出现明确的策略需求**，且该策略无法用单仓位 + 信号注入替代
3. **单仓位系统已完全稳定**，有充足的精力和时间投入重写
