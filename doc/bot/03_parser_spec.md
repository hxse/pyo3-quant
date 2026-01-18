# 信号解析规范

本文档描述 `parse_signal` 回调函数的实现细节，供实现信号解析器的开发者参考。

> [!NOTE]
> 本文档是 [01_bot_design_spec.md](./01_bot_design_spec.md) 的补充文档，专门用于指导 **解析状态的回调函数** (`parse_signal`) 的实现。
>
> **强烈推荐**：使用 Rust 编写的工具函数（通过 pyo3 暴露给 Python）来实现本规范中的所有逻辑。这不仅能保证极高的性能，还能确保与回测引擎的状态机逻辑完全一致。

> [!IMPORTANT]
> **解析器 = 纯计算、无状态**
>
> | 解析器负责 | 解析器**不**负责 |
> |------------|------------------|
> | 根据 DataFrame 输出交易意图 | 孤儿订单检查（依赖 fetch_positions） |
> | 判断进场/离场/反手信号 | 重复开仓检查 |
> | 推断离场时是否要取消SL/TP挂单 (`cancel_all_orders`) | Amount 计算 |
> | 填充价格（entry_price, sl_price, tp_price） | |
>
> 运行时检查和动态计算由**交易机器人**负责，参见 [01_bot_design_spec.md](./01_bot_design_spec.md)。

---

## 1. 接口入参

解析器回调函数签名如下：
`fn parse_signal(df: DataFrame, params: StrategyParams, index: int = -1) -> CallbackResult[SignalState]`

- **`df`**: 包含回测结果的完整 DataFrame
- **`params`**: 策略参数对象（包含 `sl_exit_in_bar`, `tp_exit_in_bar` 等配置）
- **`index`**: 指定要解析的行索引
  - `-1`: 解析最后一行（当前最新信号），用于生成交易指令
  - `-2`: 解析倒数第二行（上一根 K 线信号），用于 Bot 辅助判断（如孤儿订单检查）

---

## 2. 信号触发规则

### 2.1 核心原理

回测引擎输出已综合所有离场信号（策略信号、SL、TP、TSL、PSAR），解析器只需判断字段即可。

**源代码参考**：
- 离场逻辑：[position_calculator.rs](file:///home/hxse/pyo3-quant/src/backtest_engine/backtester/state/position_calculator.rs)
- 跳空保护：[gap_check.rs](file:///home/hxse/pyo3-quant/src/backtest_engine/backtester/state/risk_trigger/gap_check.rs)

### 2.2 进场信号

| 条件 | 含义 |
|------|------|
| `first_entry_side == 1` 且 `entry_long_price` 存在 | 多头进场 |
| `first_entry_side == -1` 且 `entry_short_price` 存在 | 空头进场 |
| `first_entry_side == 0` | 无进场 |

### 2.3 离场信号

**解析器只需处理 `risk_in_bar_direction == 0` 的情况**：

| exit_long_price | risk_in_bar_direction | 含义 | 生成动作 |
|:---------------:|:---------------------:|------|----------|
| 存在 | `0` | 多头 Next-Bar 离场 | `close_position(side=None)` |
| 存在 | `1` | 多头 In-Bar 离场 | 无动作（交易所条件单自动触发） |

| exit_short_price | risk_in_bar_direction | 含义 | 生成动作 |
|:----------------:|:---------------------:|------|----------|
| 存在 | `0` | 空头 Next-Bar 离场 | `close_position(side=None)` |
| 存在 | `-1` | 空头 In-Bar 离场 | 无动作（交易所条件单自动触发） |

### 2.4 跳空保护

回测引擎自带跳空保护（需带止损才有效，即 `Open < SL` 自动不进场），解析器无需特殊处理。

---

## 3. 方向一致性

> [!IMPORTANT]
> 信号方向与订单方向必须严格一致，不能混淆。

### 3.1 方向对应关系

| 信号方向 | 进场动作 | 离场动作 | 条件单 side |
|----------|----------|----------|-------------|
| 多头 `first_entry_side=1` | `side="long"` | `side=None` | `side="long"` |
| 空头 `first_entry_side=-1` | `side="short"` | `side=None` | `side="short"` |

> [!NOTE]
> **side 字段语义**：
> `side` 表示**持仓方向**（`long` = 多头仓位，`short` = 空头仓位），而非交易动作（buy/sell）。
> 具体的开仓买卖方向（buy/sell）由交易所 API 或回调函数内部根据 `side` 映射计算。
>
> **side 字段要求**：
> | 动作 | side 字段 |
> |------|----------|
> | `close_position` | `Optional`，保持 `None`（单仓位策略平所有仓） |
> | `cancel_all_orders` | **无** side 字段 |
> | `create_limit_order` | **必填** `"long"` 或 `"short"` |
> | `create_market_order` | **必填** `"long"` 或 `"short"` |
> | `create_stop_market_order` | **必填** `"long"` 或 `"short"` |
> | `create_take_profit_market_order` | **必填** `"long"` 或 `"short"` |

### 3.2 各场景方向说明

| 场景 | 信号字段 | 订单动作 |
|------|----------|----------|
| 多头进场 | `first_entry_side=1` + `entry_long_price` | 买入（long） |
| 多头离场 | `exit_long_price` + `risk_in_bar_direction=0` | `close_position(side=None)` |
| 多头 SL/TP | `sl_*_price_long` | 卖出条件单 |
| 空头进场 | `first_entry_side=-1` + `entry_short_price` | 卖出（short） |
| 空头离场 | `exit_short_price` + `risk_in_bar_direction=0` | `close_position(side=None)` |
| 空头 SL/TP | `sl_*_price_short` | 买入条件单 |

### 3.3 反手时的方向

反手涉及两个方向的操作，必须按顺序执行：

| 反手类型 | 第一步 | 第二步 | 第三步 |
|----------|--------|--------|---------|
| `reversal_L_to_S` | 平仓（`close_position`） | 开空（`side="short"`） | 挂空头 SL/TP |
| `reversal_S_to_L` | 平仓（`close_position`） | 开多（`side="long"`） | 挂多头 SL/TP |

> [!NOTE]
> 由于本项目是**单策略单仓位**模式，`close_position` 时 `side=None`（平掉唯一的仓位即可），无需区分方向。

### 3.4 同 Bar 风控离场（极速反手风控）

> [!IMPORTANT]
> **务必阅读状态机约束文档**
>
> 理解回测引擎的完整状态机实现是**必须**的。请务必仔细阅读 [state_machine_constraints.md](../../backtest/state_machine_constraints.md)，否则无法确保解析器与回测引擎精确对接。

根据 [state_machine_constraints.md](../../backtest/state_machine_constraints.md) 的状态机，存在 "反手后同 Bar 即触发风控" 的极端场景（状态 14 & 15）。

| 场景 | 状态名 | 含义 | 生成动作 |
|------|--------|------|----------|
| 反手开多被秒杀 | `reversal_to_L_risk` | 空平 -> 开多 -> 多头 In-Bar 风控离场 | 与普通反手相同（交易所条件单自动触发离场） |
| 反手开空被秒杀 | `reversal_to_S_risk` | 多平 -> 开空 -> 空头 In-Bar 风控离场 | 与普通反手相同（交易所条件单自动触发离场） |

**关键推论**：
对于 `reversal_to_*_risk` 信号，解析器生成的动作列表与普通 reversal 信号**完全一致**。

---

## 4. 风控模式

### 4.1 程序支持 vs 文档建议

| 模式 | 程序支持 | 文档建议 |
|------|--------|---------|
| SL In-Bar | ✅ | ✅ 推荐 |
| SL Next-Bar | ✅ | ❌ 不推荐 |
| TP In-Bar | ✅ | ❌ 不推荐 |
| TP Next-Bar | ✅ | ✅ 推荐 |
| TSL/PSAR | ✅（仅 Next-Bar） | ✅ |

**建议只使用 SL 的 In-Bar 模式**，其他都用 Next-Bar，避免 SL/TP 交易所无法自动联动取消的问题。

### 4.2 条件单

#### 风控价格类型

| 类型 | 字段名格式 | 说明 |
|------|-----------|------|
| 百分比 SL | `sl_pct_price_long/short` | 基于进场价百分比计算 |
| ATR SL | `sl_atr_price_long/short` | 基于 ATR 指标计算 |
| 百分比 TP | `tp_pct_price_long/short` | 基于进场价百分比计算 |
| ATR TP | `tp_atr_price_long/short` | 基于 ATR 指标计算 |

> [!TIP]
> **完整字段清单**：DataFrame 所有输出列的定义请参考 [output_columns.md](../backtest/output_columns.md)。

> [!NOTE]
> - 字段命名规则：`{sl|tp}_{type}_price_{long|short}`，其中 `type` ∈ {pct, atr}
> - **所有条件单都是独立判断的**，只要字段存在就生成挂单动作，不互斥
> - **支持任意数量 SL/TP**：如同时存在 `sl_pct_price_long` 和 `sl_atr_price_long`，则生成两个 SL 条件单，全部挂上, tp也是同理

> [!IMPORTANT]
> **TSL/PSAR 不是条件单**
>
> TSL（跟踪止损）和 PSAR 只有 Next-Bar 模式，因此**不生成 TSL/PSAR 条件单动作**。解析器无需关注 TSL/PSAR 的特定字段，只需关注通用的 `exit_*_price` + `risk_in_bar_direction=0` 判断离场即可。

#### 提交条件

条件单只在**同方向进场时生成一次**，不是每根 K 线都生成：

1. 确认同方向进场信号满足（`first_entry_side != 0`）
2. 同时满足：`params.sl_exit_in_bar = True` **且** `sl_*_price_long/short` 存在
3. 或：`params.tp_exit_in_bar = True` **且** `tp_*_price_long/short` 存在

> [!NOTE]
> **TP/SL Next-Bar 模式行为说明**：
> 如果配置为 `tp_exit_in_bar = False` 或 `sl_exit_in_bar = False`，解析器**不会生成对应的条件单**。
> 它们的触发完全依赖于回测引擎在下一根 K 线（或后续 K 线）检测到离场信号（`exit_*_price` 存在），从而在 **Next-Bar** 生成 `close_position` 动作。

---

## 5. 反手支持

### 5.1 反手操作顺序

反手操作遵循状态机顺序（参考 [state_machine_constraints.md](file:///home/hxse/pyo3-quant/doc/backtest/state_machine_constraints.md)）：

**动作生成顺序**：先 `close_position` → 后 `create_*_order` → 最后 `create_stop/tp_order`

同 bar 最复杂的场景需要生成的动作：
1. `close_position` - 平掉上一根 K 线信号的仓位
2. `create_limit/market_order` - 按上一根 K 线信号开反向仓位
3. `create_stop_market_order` / `create_take_profit_market_order` - 对新开仓位挂 SL/TP

### 5.2 反手状态

| 状态 | 含义 |
|------|------|
| `reversal_L_to_S` | 多头平仓 + 开空 |
| `reversal_S_to_L` | 空头平仓 + 开多 |
| `reversal_to_L_risk` | 反手开多后同 bar In-Bar 风控触发 |
| `reversal_to_S_risk` | 反手开空后同 bar In-Bar 风控触发 |

### 5.3 反手与平仓时的挂单清理

无论是**反手**还是**普通离场**，解析器在生成 `close_position` 动作时，**一律追加 `cancel_all_orders`**。

> [!TIP]
> **简化设计**：离场 = `close_position` + `cancel_all_orders`，无需判断之前是否挂过条件单。虽然可能冗余，但更安全。

**反手时生成的动作序列**：
1. `close_position` - 先执行平仓，确保不再持有反向仓位
2. `cancel_all_orders` - 取消原方向的所有条件单（SL/TP），防止误触
3. `create_limit/market_order` - 执行开仓
4. `create_stop_market_order` / `create_take_profit_market_order` - 挂新方向的条件单

> [!NOTE]
> **顺序原因**：先平仓再取消挂单更安全。如果先取消 SL，在平仓失败的情况下，会导致裸奔（无止损持仓）。反之，虽然先平仓可能导致极短时间内"无仓位有挂单"，但由于紧接着就会取消挂单，且挂单通常是远离现价的（特别是止损），风险远小于裸奔。

---

## 6. 订单执行细节

### 6.1 进场订单

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `entry_order_type` | `str` | `"limit"` | 进场订单类型：`"limit"` 或 `"market"` |

**限价进场**：使用当前 K 线开盘价精准进场。

**市价进场**：直接市价进场。由于每秒检测一次，与开盘价差异不大；加上跳空保护，滑点风险可接受。

### 6.2 限价单超时检查

只有当**前一根有限价进场**时，才在新周期开始时检查：
1. 检查限价订单是否成交
2. 如未成交，生成 `cancel_all_orders` 动作
3. 如有孤儿挂单，一并取消

**不补单**：错过成交意味着行情剧烈，错过可接受。如有补单需求，用户可自行在回调函数中实现相关逻辑。

### 6.3 离场订单

**类型**：`close_position`（市价平仓）

**触发条件**：`exit_*_price` 存在 且 `risk_in_bar_direction == 0`

---

## 7. SignalState 生成示例

### 7.1 普通多头进场

```python
SignalState(
    actions=[
        SignalAction(action_type="create_limit_order", symbol="BTC/USDT", side="long", price=50000),
        SignalAction(action_type="create_stop_market_order", symbol="BTC/USDT", side="long", price=49000),
    ],
    has_exit=False,
)
```

### 7.2 多头离场

```python
SignalState(
    actions=[
        SignalAction(action_type="close_position", symbol="BTC/USDT"),
        SignalAction(action_type="cancel_all_orders", symbol="BTC/USDT"),
    ],
    has_exit=True,  # 标记有离场，用于触发孤儿订单检查
)
```

### 7.3 反手（多转空）

```python
SignalState(
    actions=[
        SignalAction(action_type="close_position", symbol="BTC/USDT"),
        SignalAction(action_type="cancel_all_orders", symbol="BTC/USDT"),
        SignalAction(action_type="create_limit_order", symbol="BTC/USDT", side="short", price=50000),
        SignalAction(action_type="create_stop_market_order", symbol="BTC/USDT", side="short", price=51000),
    ],
    has_exit=True,  # 反手包含离场动作，需要清理旧挂单
)
```

### 7.4 In-Bar 条件单触发离场（无动作，但标记有离场）

```python
SignalState(
    actions=[],  # 无动作，交易所条件单自动触发
    has_exit=True,  # 但标记有离场，供 Bot 孤儿检查使用
)
```

### 7.5 无操作

```python
SignalState(
    actions=[],
    has_exit=False,
)

```

---

## 8. 逻辑决策流程图（解析器内部）

本流程图仅展示 `parse_signal` **解析器内部** 的决策逻辑，不包含 Bot 的外部循环和运行时检查。

```mermaid
flowchart TD
    START([输入: DataFrame, params, index]) --> GET_ROW[获取指定行 index 的数据]
    GET_ROW --> INIT_EXIT[has_exit = False]
    INIT_EXIT --> REVERSAL{是反手信号?}

    REVERSAL --> |是| SET_EXIT_REV[has_exit = True]
    SET_EXIT_REV --> ACT_CLOSE_REV[+ close_position]
    ACT_CLOSE_REV --> ACT_CANCEL_REV[+ cancel_all_orders]
    ACT_CANCEL_REV --> ACT_OPEN_REV[+ create_limit/market_order]
    ACT_OPEN_REV --> CHECK_SL

    REVERSAL --> |否| EXIT{是离场信号?}

    EXIT --> |是, Next-Bar| SET_EXIT_NEXT[has_exit = True]
    SET_EXIT_NEXT --> ACT_CLOSE[+ close_position]
    ACT_CLOSE --> ACT_CANCEL_EXIT[+ cancel_all_orders]
    ACT_CANCEL_EXIT --> RETURN([返回: SignalState])

    EXIT --> |是, In-Bar| SET_EXIT_INBAR[has_exit = True<br/>actions 保持空]
    SET_EXIT_INBAR --> RETURN

    EXIT --> |否| ENTRY{是进场信号?}

    ENTRY --> |是| ACT_OPEN[+ create_limit/market_order]
    ACT_OPEN --> CHECK_SL{sl_in_bar<br/>+ sl_price存在?}

    CHECK_SL --> |是| ACT_SL[+ create_stop_market_order]
    CHECK_SL --> |否| CHECK_TP
    ACT_SL --> CHECK_TP{tp_in_bar<br/>+ tp_price存在?}

    CHECK_TP --> |是| ACT_TP[+ create_take_profit_market_order]
    ACT_TP --> RETURN
    CHECK_TP --> RETURN

    ENTRY --> |否| EMPTY[actions=[]]
    EMPTY --> RETURN
```
