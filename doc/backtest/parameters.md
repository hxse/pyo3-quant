# 回测参数 (Backtest Parameters)

本文档详细说明 `BacktestParams` 结构体中所有可配置参数的含义、取值范围及作用。

## 1. 资金管理 (Capital & Fees)

| 参数名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| `initial_capital` | `float` | 初始本金（USD）。回测开始时的账户资金量。 | 必须 > 0.0 |
| `fee_fixed` | `float` | 固定手续费。每笔交易（离场时结算）的固定费用。 | 必须 >= 0.0 |
| `fee_pct` | `float` | 百分比手续费。每笔交易金额的百分比费用。 | 必须 >= 0.0 |

> [!NOTE]
> **手续费机制**：手续费在**离场时**统一扣除。`fee` 列记录单笔交易的费用，`fee_cum` 列记录历史累计费用。

---

## 2. 风控参数 (Risk Management)

所有风控参数均为 `Optional[Param]` 类型。如果未设置或值为 `<= 0.0`，则对应的功能不会启用。

| 参数名 | 说明 |
|--------|------|
| `sl_pct` | **百分比止损**。当亏损达到 `entry_price * pct` 时触发。<br>公式：`entry * (1 - sign * sl_pct)` |
| `tp_pct` | **百分比止盈**。当盈利达到 `entry_price * pct` 时触发。<br>公式：`entry * (1 + sign * tp_pct)` |
| `tsl_pct` | **百分比跟踪止损**。当从持仓期间极值回撤达到 `pct` 时触发。<br>公式：`extremum * (1 - sign * tsl_pct)` |
| `sl_atr` | **ATR 止损**。基于 ATR 的动态止损。<br>公式：`entry - sign * atr * k` |
| `tp_atr` | **ATR 止盈**。基于 ATR 的动态止盈。<br>公式：`entry + sign * atr * k` |
| `tsl_atr` | **ATR 跟踪止损**。基于 ATR 的动态跟踪止损。<br>公式：`extremum - sign * atr * k` |

> [!IMPORTANT]
> **ATR 依赖**：如果使用了任何 `*_atr` 参数，必须同时设置 `atr_period` 且 `atr_period > 0`。

### PSAR 跟踪止损参数

PSAR (Parabolic SAR) 是一种特殊的跟踪止损算法。以下三个参数**必须同时存在**才能启用：

1. `tsl_psar_af0`: 初始加速因子 (Acceleration Factor)
2. `tsl_psar_af_step`: 加速因子步进
3. `tsl_psar_max_af`: 最大加速因子

---

## 3. 执行参数 (Execution)

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|:----:|------|
| `exit_in_bar` | `bool` | `False` | **离场时机选择**。<br>`True`: 允许在 K 线内部（In-Bar）立即离场（以触发价成交）。<br>`False`: 延迟到下一根 K 线开盘（Next-Bar）离场。 |
| `use_extrema_for_exit` | `bool` | `False` | **价格检查源**。<br>`True`: 使用 High/Low 检查止损止盈。<br>`False`: 使用 Close 检查止损止盈。 |
| `tsl_atr_tight` | `bool` | `False` | **ATR 跟踪止损更新模式**。<br>`True`: 每根 K 线都尝试收紧止损线。<br>`False`: 仅当创新高/新低时才收紧止损线。 |

### `exit_in_bar` 的影响

- **In-Bar (True)**: 更灵敏，减少滑点风险，但通过 `risk_in_bar_direction` 标记。
- **Next-Bar (False)**: 更保守，总是以次日开盘价成交。

---

## 4. 指标参数 (Indicators)

| 参数名 | 类型 | 说明 |
|--------|------|------|
| `atr_period` | `Optional[Param]` | **ATR 周期**。计算 ATR 指标的窗口长度。<br>仅当使用 ATR 相关风控参数时必须。 |
