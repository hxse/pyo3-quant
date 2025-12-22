# 风控管理 (Risk Management)

回测引擎提供了一套多层级、可配置的风控系统，支持从简单的固定止损到复杂的动态跟踪止损。

## 1. 核心机制

### 1.1 初始化规则
- **时机**：所有的风控价格阈值（SL/TP/TSL）都在**进场当根 K 线 (Entry Bar)** 立即计算并初始化。
- **依据**：使用进场价格 (`entry_price`) 作为基准。
- **持久化**：一旦初始化，阈值会保存在状态机中，直至于离场。对于跟踪止损，阈值会随价格变动而更新。

### 1.2 In-Bar vs Next-Bar 离场
风控触发后的离场行为由参数 `exit_in_bar` 控制：

1.  **In-Bar 模式 (`exit_in_bar = True`)**：
    -   如果当根 K 线内的价格触碰了风控线，**立即在当根 K 线离场**。
    -   离场价格 = 触发价格 (SL/TP/TSL 阈值)。
    -   **标志**：`risk_in_bar_direction` 会被设置为 `1` (多头) 或 `-1` (空头)。

2.  **Next-Bar 模式 (`exit_in_bar = False`)**：
    -   即使当根 K 线触发了风控，也会**延迟到下一根 K 线开盘**离场。
    -   离场价格 = Next Bar Open。
    -   **标志**：`risk_in_bar_direction` 保持为 `0`（与策略信号离场一致）。

> [!IMPORTANT]
> **`risk_in_bar_direction`** 是区分 "风控强制离场(In-Bar)" 与 "普通离场(策略/Next-Bar)" 的唯一可靠标志。

---

## 2. 止损/止盈方式详解

系统支持多空分离的风控计算。以下公式中：
- `sign`：多头为 `1`，空头为 `-1`。
- `k`：用户配置的倍数参数。

### 2.1 固定百分比 (Fixed Percentage)

最基础的风控方式，基于进场价格设定固定的百分比幅度。

- **止损 (SL Pct)**: `SL = entry * (1 - sign * pct)`
- **止盈 (TP Pct)**: `TP = entry * (1 + sign * pct)`

### 2.2 基于 ATR (ATR-Based)

使用进场时的 ATR 值来适应市场波动率。

- **止损 (SL ATR)**: `SL = entry - sign * atr * k`
- **止盈 (TP ATR)**: `TP = entry + sign * atr * k`

### 2.3 跟踪止损 (Trailing Stop)

跟踪止损线会随着价格向有利方向移动而移动，锁定利润。

**机制**：
1.  记录持仓期间的极值价格 `extremum` (多头记录最高价，空头记录最低价)。
2.  当 `extremum` 更新时，重新计算 TSL 阈值。
3.  **单向移动原则**：多头 TSL 只能上移，空头 TSL 只能下移。

**公式**：
- **百分比跟踪**: `TSL = extremum * (1 - sign * pct)`
- **ATR 跟踪**: `TSL = extremum - sign * current_atr * k`
- **PSAR 跟踪**: 使用标准的抛物线转向指标算法。

---

## 3. 触发优先级

当一根 K 线内同时满足多个风控条件时，引擎按以下顺序检查触发：

1.  **止损 (SL)**: 优先检查，保护本金最重要。
2.  **止盈 (TP)**: 其次检查。
3.  **跟踪止损 (TSL)**: 最后检查。

> [!NOTE]
> 在 **Next-Bar 模式**下，优先级的意义较小，因为都是在下一根 K 线开盘离场。但在 **In-Bar 模式**下，由于离场价格不同，优先级决定了最终的盈亏。

---

## 4. 多空分离设计

引擎内部的 `RiskState` 对多头和空头维护完全独立的状态：
- `sl_pct_price_long` vs `sl_pct_price_short`
- `highest_since_entry` (Long) vs `lowest_since_entry` (Short)

这意味着理论上引擎支持同时持有多空仓位（虽然目前策略层限制为单仓位）。这种设计为未来的锁仓或对冲功能预留了空间。
