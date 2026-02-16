# 回测输出列 (Output Columns)

回测结果返回一个 Polars DataFrame，包含以下列。

## 1. 固定列 (Fixed Columns)

无论使用什么参数，这些列总是存在。

### 资金状态
| 列名 | 类型 | 说明 |
|------|------|------|
| `balance` | `float64` | **账户余额**。仅在交易平仓时更新，包含已实现盈亏。 |
| `equity` | `float64` | **账户净值**。每根 K 线更新，包含未实现盈亏 (`balance + unrealized_pnl`)。 |
| `current_drawdown` | `float64` | **当前回撤**。当前净值相对于历史最高净值的回撤比例 (0 ~ 1)。 |
| `trade_pnl_pct` | `float64` | **单笔交易回报率**。仅在离场 K 线有值，其余为 0。 |
| `total_return_pct` | `float64` | **累计回报率**。基于初始本金的累计收益百分比。 |
| `fee` | `float64` | **单笔手续费**。仅在离场 K 线有值。 |
| `fee_cum` | `float64` | **累计手续费**。历史所有交易手续费的总和。 |

### 价格与交易
| 列名 | 类型 | 说明 |
|------|------|------|
| `entry_long_price` | `float64` | 多头进场价格 (NaN 表示无操作)。 |
| `entry_short_price` | `float64` | 空头进场价格 (NaN 表示无操作)。 |
| `exit_long_price` | `float64` | 多头离场价格 (NaN 表示无操作)。 |
| `exit_short_price` | `float64` | 空头离场价格 (NaN 表示无操作)。 |
| `risk_in_bar_direction` | `int8` | **风控离场标志**。<br>`0`: 无 In-Bar 风控离场。<br>`1`: 多头 In-Bar 风控触发。<br>`-1`: 空头 In-Bar 风控触发。 |
| `first_entry_side` | `int8` | **首次进场方向**。<br>`0`: 非进场 bar。<br>`1`: 多头首次进场。<br>`-1`: 空头首次进场。 |
| `frame_state` | `uint8` | **帧状态枚举**。<br>从价格字段组合**推断**而出的状态标识（0=no_position, ..., 15=gap_blocked, 16=capital_exhausted）。<br>⚠️ **注意**：此列是只读输出，**不是**状态机的驱动源。状态机是由价格字段驱动的。 |

> [!TIP]
> **如何识别持仓状态？**
> - 持有多头: `entry_long_price` 有值 且 `exit_long_price` 为 NaN。
> - 持有空头: `entry_short_price` 有值 且 `exit_short_price` 为 NaN。

---

## 2. 可选列 (Optional Columns)

这些列仅在对应的参数有效时才会出现在 DataFrame 中。可选列的生成逻辑定义在 `OutputBuffers::new()` 中。

### 判断逻辑

| 条件 | 输出列 |
|------|--------|
| `is_sl_pct_param_valid()` = true | `sl_pct_price_long`, `sl_pct_price_short` |
| `is_tp_pct_param_valid()` = true | `tp_pct_price_long`, `tp_pct_price_short` |
| `is_tsl_pct_param_valid()` = true | `tsl_pct_price_long`, `tsl_pct_price_short` |
| `is_sl_atr_param_valid()` = true | `sl_atr_price_long`, `sl_atr_price_short` |
| `is_tp_atr_param_valid()` = true | `tp_atr_price_long`, `tp_atr_price_short` |
| `is_tsl_atr_param_valid()` = true | `tsl_atr_price_long`, `tsl_atr_price_short` |
| `is_tsl_psar_param_valid()` = true | `tsl_psar_price_long`, `tsl_psar_price_short` |

### 百分比风控列
- `sl_pct_price_long`, `sl_pct_price_short`
- `tp_pct_price_long`, `tp_pct_price_short`
- `tsl_pct_price_long`, `tsl_pct_price_short`

### ATR 风控列
- `atr` (ATR 指标值，仅当有任一 ATR 参数有效时输出)
- `sl_atr_price_long`, `sl_atr_price_short`
- `tp_atr_price_long`, `tp_atr_price_short`
- `tsl_atr_price_long`, `tsl_atr_price_short`

### PSAR 风控列
- `tsl_psar_price_long`, `tsl_psar_price_short`

> [!NOTE]
> 可选列通常用于调试和可视化，验证风控线是否按预期计算和移动。在生产环境如果不关心风控线轨迹，可以忽略这些列。

### 输入透传列

- `has_leading_nan`（`bool`）：仅当输入 `signals_df` 存在该列时，回测输出才会透传该列。

---

## 3. 列值约定

### 价格列的 NaN 含义

| 列 | 值为 NaN 的含义 |
|----|----------------|
| `entry_long_price` | 当前 bar 无多头持仓 |
| `exit_long_price` | 当前 bar 未平多头仓位 |
| 风控价格列 (如 `sl_pct_price_long`) | 当前 bar 无对应方向持仓 |

### 状态推断组合

| 场景 | 判断条件 |
|------|----------|
| 持有多头 | `entry_long_price` 非 NaN 且 `exit_long_price` 为 NaN |
| 多头首次进场 bar | `first_entry_side == 1` |
| 多头被风控平仓 | `risk_in_bar_direction == 1` |
| 多头秒杀（进即出） | `first_entry_side == 1` 且 `risk_in_bar_direction == 1` |
