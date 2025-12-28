# 风控管理 (Risk Management)

回测引擎提供了一套多层级、可配置的风控系统，支持从简单的固定止损到复杂的动态跟踪止损。

## 1. 核心机制

### 1.1 初始化规则
- **时机**：所有的风控价格阈值（SL/TP/TSL/PSAR）都在**进场当根 K 线 (Entry Bar)** 立即计算并初始化。
- **数据源**：为了避免未来数据泄露，计算使用 **信号 Bar (Signal Bar / Prev Bar)** 的数据。
    - **基准价格**：使用信号 Bar 的收盘价 (`signal_bar.close`)。
    - **ATR**：使用信号 Bar 的 ATR (`signal_bar.atr`)。
- **进场基准**：虽然风控计算基于信号 Bar，但在 TSL 初始化时，极值 (`extremum`) 的追踪仍以进场价格 (`entry_price` / `current_bar.open`) 为起点。
- **持久化**：一旦初始化，阈值会保存在状态机中，直至离场。对于跟踪止损（TSL/PSAR），阈值会随价格变动而更新。

### 1.2 风控类型分类

| 类型 | 离场时机 | 受 `exit_in_bar` 影响 | 备注 |
|------|---------|---------------------|------|
| **SL (止损)** | sl_pct, sl_atr | ✅ 是 | In-Bar 可当根离场 |
| **TP (止盈)** | tp_pct, tp_atr | ✅ 是 | In-Bar 可当根离场 |
| **TSL (跟踪止损)** | tsl_pct, tsl_atr | ❌ 否 | 始终 Next-Bar 离场 |
| **PSAR (抛物线跟踪)** | tsl_psar_* | ❌ 否 | 始终 Next-Bar 离场 |

> [!IMPORTANT]
> **`exit_in_bar` 只影响 SL/TP**，不影响 TSL 和 PSAR。TSL/PSAR 始终在下一根 K 线开盘价离场。

---

## 2. 关键参数详解

### 2.1 `exit_in_bar` - 离场时机

**作用范围**：仅影响 **SL (止损)** 和 **TP (止盈)**

| 值 | SL/TP 行为 | TSL/PSAR 行为 |
|----|-----------|--------------|
| `True` | 当根 K 线内触发即离场，使用触发价格 | 不受影响，始终 Next-Bar 开盘价离场 |
| `False` | 延迟到下一根 K 线开盘离场 | 不受影响，始终 Next-Bar 开盘价离场 |

**标志位**：`risk_in_bar_direction`
- `1` = 多头 In-Bar 离场
- `-1` = 空头 In-Bar 离场
- `0` = Next-Bar 离场（策略信号离场 / TSL 触发 / `exit_in_bar=False`）

### 2.2 触发模式 (Trigger Mode)

**作用范围**：影响 **触发判断** 所使用的价格

| 参数 | 说明 |
|------|------|
| `sl_trigger_mode` | SL 触发检测。`False`=close, `True`=high/low |
| `tp_trigger_mode` | TP 触发检测。`False`=close, `True`=high/low |
| `tsl_trigger_mode` | TSL 触发检测(含psar)。`False`=close, `True`=high/low |

**注意**：此参数影响的是"**是否触发**"的判断，而非离场价格本身。

### 2.3 锚点模式 (Anchor Mode)

**作用范围**：影响 **价格阈值计算** 所使用的锚点

| 参数 | 说明 |
|------|------|
| `sl_anchor_mode` | SL 锚点。`False`=close, `True`=high/low (多头用low，空头用high) |
| `tp_anchor_mode` | TP 锚点。`False`=close, `True`=high/low (多头用high，空头用low) |
| `tsl_anchor_mode` | TSL 锚点(不含psar)。`False`=close, `True`=extremum |

### 2.4 `tsl_atr_tight` - 跟踪止损更新模式

**作用范围**：仅影响 **TSL-ATR (tsl_atr)**

| 值 | 更新条件 |
|----|---------|
| `False` (默认) | 只有价格突破新高/新低时才更新 TSL 价格 |
| `True` | 每根 K 线都尝试更新 TSL 价格（更紧密跟踪） |

**注意**：无论设置如何，TSL 始终遵循**单向移动原则**（多头只能上移，空头只能下移）。

---

## 3. 悲观取值规则

当一根 K 线内**同时触发多个风控条件**时，需要选择一个离场价格。

### 3.1 In-Bar 模式 (`exit_in_bar=True`)

**只有 SL/TP 参与悲观取值**（因为只有它们支持 In-Bar 离场）：

- **多头**：选择触发价格中**最小的**（亏损最大）
- **空头**：选择触发价格中**最大的**（亏损最大）

**示例**：多头持仓，同时触发：
- `sl_pct_price` = 9.5
- `sl_atr_price` = 9.3

→ 选择 9.3（更低，亏更多）

> [!NOTE]
> TSL/PSAR 不参与 In-Bar 悲观取值，因为它们始终用 Next-Bar 开盘价离场。

### 3.2 Next-Bar 模式

当 `exit_in_bar=False`，或者只有 TSL/PSAR 触发时：

- **离场价格** = 下一根 K 线开盘价（统一的）
- **无需悲观取值**（反正都是同一个价格）

### 3.3 触发优先级

当多种风控同时触发时：

1. **In-Bar 优先**：如果 SL/TP 触发了 In-Bar 离场，则当根 K 线离场，不等待 TSL
2. **TSL/PSAR**：始终按 Next-Bar 处理（下一根 K 线开盘价离场）

> [!NOTE]
> 悲观取值自然会让止损价格（通常更亏）优先于止盈价格，无需额外的 SL/TP 优先级规则。

---

## 4. 止损/止盈方式详解

### 1. 百分比止损 (SL PCT)
- **公式**：`SL = signal_close * (1 - sign * sl_pct)`
    - 多头：`SL = signal_close * (1 - sl_pct)`
    - 空头：`SL = signal_close * (1 + sl_pct)`

### 2. ATR 止损 (SL ATR)
- **公式**：`SL = signal_close - sign * signal_atr * sl_atr`
    - 多头：`SL = signal_close - signal_atr * sl_atr`
    - 空头：`SL = signal_close + signal_atr * sl_atr`

### 3. 百分比止盈 (TP PCT)
- **公式**：`TP = signal_close * (1 + sign * tp_pct)`

### 4. ATR 止盈 (TP ATR)
- **公式**：`TP = signal_close + sign * signal_atr * tp_atr`

其中 `k` 为用户配置的倍数参数。

### 4.3 跟踪止损 (Trailing Stop)

跟踪止损线会随着价格向有利方向移动而移动，锁定利润。

**机制**：
1. 记录持仓期间的极值价格 `extremum`（多头记录最高价，空头记录最低价）
2. 当 `extremum` 更新时，重新计算 TSL 阈值（受 `tsl_atr_tight` 影响，见 2.3 节）
3. **单向移动原则**：多头 TSL 只能上移，空头 TSL 只能下移

**公式**：
- **百分比跟踪 (TSL Pct)**: `TSL = extremum × (1 - sign × pct)`
- **ATR 跟踪 (TSL ATR)**: `TSL = extremum - sign × current_atr × k`

### 4.4 PSAR 跟踪止损 (Parabolic SAR)

使用标准的抛物线转向指标算法作为跟踪止损。

**参数**：
- `tsl_psar_af0`：初始加速因子（默认 0.02）
- `tsl_psar_af_step`：加速因子步进（默认 0.02）
- `tsl_psar_max_af`：最大加速因子（默认 0.2）

**特点**：
- 比固定百分比/ATR 更动态，能适应趋势加速
- 始终使用 Next-Bar 模式离场
- 三个参数必须同时配置或同时不配置

---

## 5. 多空分离设计

引擎内部的 `RiskState` 对多头和空头维护完全独立的状态：

- `sl_pct_price_long` vs `sl_pct_price_short`
- `tsl_psar_price_long` vs `tsl_psar_price_short`
- `highest_since_entry` (Long) vs `lowest_since_entry` (Short)

这意味着理论上引擎支持同时持有多空仓位（虽然目前策略层限制为单仓位）。
## 6. 跳空保护 (Gap Protection)

为了更贴近实盘交易中的"限价单"或"安全过滤"行为，系统实施了跳空保护机制：

- **机制**：在确认进场前，系统会检查进场 Bar 的开盘价 (`Entry Open`) 是否已经穿过了基于信号 Bar 计算出的风控价格。
- **检查范围**：SL PCT/ATR、TP PCT/ATR、TSL PCT/ATR、TSL PSAR（共7种）
- **逻辑**：
    - **做多**：如果 `Entry Open < SL` 或 `Entry Open < TSL` 或 `Entry Open < PSAR` 或 `Entry Open > TP`，则**跳过**该次进场。
    - **做空**：如果 `Entry Open > SL` 或 `Entry Open > TSL` 或 `Entry Open > PSAR` 或 `Entry Open < TP`，则**跳过**该次进场。
- **对比**：这与 `backtesting.py` 的默认行为不同（后者会进场并立即止损），但通过使用无跳空的数据，两者的结果可以保持一致。
