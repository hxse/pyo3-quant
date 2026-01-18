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

| 类型 | 离场时机 | 受 `sl/tp_exit_in_bar` 影响 | 备注 |
|------|---------|---------------------|------|
| **SL (止损)** | sl_pct, sl_atr | ✅ 是 (sl_exit_in_bar) | In-Bar 可当根离场 |
| **TP (止盈)** | tp_pct, tp_atr | ✅ 是 (tp_exit_in_bar) | In-Bar 可当根离场 |
| **TSL (跟踪止损)** | tsl_pct, tsl_atr | ❌ 否 | 始终 Next-Bar 离场 |
| **PSAR (抛物线跟踪)** | tsl_psar_* | ❌ 否 | 始终 Next-Bar 离场 |

> [!IMPORTANT]
> **`sl_exit_in_bar` / `tp_exit_in_bar`** 分别独立控制 SL 和 TP 的离场行为。TSL/PSAR 始终在下一根 K 线开盘价离场。

> [!NOTE]
> **所有风控类型都是独立判断的**，无论是 SL/TP/TSL，还是 pct/atr/psar，只要配置了就会计算并参与触发检测，不互斥。

---

## 2. 关键参数详解

### 2.1 `sl_exit_in_bar` / `tp_exit_in_bar` - 离场时机

**作用范围**：分别控制 **SL (止损)** 和 **TP (止盈)**

| 值 | 对应 SL/TP 行为 | TSL/PSAR 行为 |
|----|-----------|--------------|
| `True` | 当根 K 线内触发即离场，使用触发价格 | 不受影响，始终 Next-Bar 开盘价离场 |
| `False` | 延迟到下一根 K 线开盘离场 | 不受影响，始终 Next-Bar 开盘价离场 |

**标志位**：`risk_in_bar_direction`
- `1` = 多头 In-Bar 离场
- `-1` = 空头 In-Bar 离场
- `0` = Next-Bar 离场（策略信号离场 / TSL 触发 / `sl/tp_exit_in_bar=False`）

### 2.2 触发模式 (Trigger Mode)

**作用范围**：影响 **触发判断** 所使用的价格

| 参数 | 影响的风控类型 | 说明 |
|------|--------------|------|
| `sl_trigger_mode` | SL PCT, SL ATR | SL 触发检测。`False`=close, `True`=high/low |
| `tp_trigger_mode` | TP PCT, TP ATR | TP 触发检测。`False`=close, `True`=high/low |
| `tsl_trigger_mode` | TSL PCT, TSL ATR, **TSL PSAR** | TSL 触发检测。`False`=close, `True`=high/low |

**注意**：此参数影响的是"是否触发"的判断，而非离场价格本身。

### 2.3 锚点模式 (Anchor Mode)

**作用范围**：影响 **价格阈值计算** 所使用的锚点

| 参数 | 影响的风控类型 | 说明 |
|------|--------------|------|
| `sl_anchor_mode` | SL PCT, SL ATR | SL 锚点。`False`=close, `True`=high/low (多头用low，空头用high) |
| `tp_anchor_mode` | TP PCT, TP ATR | TP 锚点。`False`=close, `True`=high/low (多头用high，空头用low) |
| `tsl_anchor_mode` | TSL PCT, TSL ATR, **TSL PSAR** | TSL 锚点。`False`=close, `True`=high/low (extremum) |

> [!IMPORTANT]
> `tsl_anchor_mode` 现在统一影响所有三种 TSL 类型（PCT、ATR、PSAR）的价格计算方式。

### 2.4 `tsl_atr_tight` - 跟踪止损更新模式

**作用范围**：仅影响 **TSL-ATR (tsl_atr)**

| 值 | 更新条件 |
|----|---------|
| `False` (默认) | 只有价格突破新高/新低时才更新 TSL 价格 |
| `True` | 每根 K 线都尝试更新 TSL 价格（更紧密跟踪） |

**注意**：无论设置如何，TSL 始终遵循**单向移动原则**（多头只能上移，空头只能下移）。

---

## 2.5 参数使用矩阵（完整参考）

以下表格完整展示了每种风控类型在各阶段使用的参数：

### SL (止损)

| 类型 | 初始化 (Init) | 更新 (Update) | 触发检测 (Trigger) |
|------|-------------|-------------|----------------|
| **SL PCT** | `sl_anchor_mode` | N/A (不更新) | `sl_trigger_mode` |
| **SL ATR** | `sl_anchor_mode` | N/A (不更新) | `sl_trigger_mode` |

### TP (止盈)

| 类型 | 初始化 (Init) | 更新 (Update) | 触发检测 (Trigger) |
|------|-------------|-------------|----------------|
| **TP PCT** | `tp_anchor_mode` | N/A (不更新) | `tp_trigger_mode` |
| **TP ATR** | `tp_anchor_mode` | N/A (不更新) | `tp_trigger_mode` |

### TSL (跟踪止损)

| 类型 | 初始化 (Init) | 更新 (Update) | 触发检测 (Trigger) |
|------|-------------|-------------|----------------|
| **TSL PCT** | `tsl_anchor_mode` | `tsl_anchor_mode` | `tsl_trigger_mode` |
| **TSL ATR** | `tsl_anchor_mode` | `tsl_anchor_mode` | `tsl_trigger_mode` |
| **TSL PSAR** | `tsl_anchor_mode` | `tsl_anchor_mode` | `tsl_trigger_mode` |

> [!NOTE]
> - **Init**：进场时计算初始风控价格，发生在 `gap_check.rs`
> - **Update**：持仓期间更新风控价格，发生在 `threshold_updater.rs`
> - **Trigger**：检测是否触发离场，发生在 `trigger_checker.rs`

---

## 3. 悲观取值规则

当一根 K 线内**同时触发多个风控条件**时，需要选择一个离场价格。

### 3.1 In-Bar 模式 (`sl/tp_exit_in_bar=True`)

**只有配置了 In-Bar 的 SL/TP 参与悲观取值**：

- **多头**：选择触发价格中**最小的**（亏损最大）
- **空头**：选择触发价格中**最大的**（亏损最大）

**示例**：多头持仓，同时触发：
- `sl_pct_price` = 9.5 (In-Bar)
- `sl_atr_price` = 9.3 (In-Bar)

→ 选择 9.3（更低，亏更多）

> [!NOTE]
> TSL/PSAR 或 配置为 Next-Bar 的 SL/TP 不参与 In-Bar 悲观取值。

### 3.2 Next-Bar 模式

当所有触发的风控都配置为 `False` (Next-Bar)，或者只有 TSL/PSAR 触发时：

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
- **`tsl_anchor_mode`** 控制 PSAR 计算时使用 High/Low 还是 Close
- **`tsl_trigger_mode`** 控制 PSAR 触发检测时使用 High/Low 还是 Close

---

## 5. 多空分离设计

引擎内部的 `RiskState` 对多头和空头维护完全独立的状态：

- `sl_pct_price_long` vs `sl_pct_price_short`
- `tsl_psar_price_long` vs `tsl_psar_price_short`
- `long_anchor_since_entry` (Long) vs `short_anchor_since_entry` (Short)

> [!NOTE]
> 锚点字段 (`*_anchor_since_entry`) 用于跟踪止损计算，根据 `tsl_anchor_mode` 的设置可能是 `close` 或 `high/low`。

这意味着理论上引擎支持同时持有多空仓位（虽然目前策略层限制为单仓位）。

---

## 6. 跳空保护 (Gap Protection)

为了更贴近实盘交易中的"限价单"或"安全过滤"行为，系统实施了跳空保护机制。

### 6.1 机制说明

在确认进场前，系统会检查进场 Bar 的开盘价 (`Entry Open`) 是否已经穿过了基于信号 Bar 计算出的风控价格。

### 6.2 检查范围

| 风控类型 | 检查条件 |
|----------|----------|
| SL PCT | `entry_open` 是否穿过 `sl_pct_price` |
| SL ATR | `entry_open` 是否穿过 `sl_atr_price` |
| TP PCT | `entry_open` 是否穿过 `tp_pct_price` |
| TP ATR | `entry_open` 是否穿过 `tp_atr_price` |
| TSL PCT | `entry_open` 是否穿过 `tsl_pct_price` |
| TSL ATR | `entry_open` 是否穿过 `tsl_atr_price` |
| TSL PSAR | `entry_open` 是否穿过初始 `psar_price` |

### 6.3 跳过逻辑

| 方向 | 跳过条件 |
|------|----------|
| **做多** | `Entry Open < SL` 或 `Entry Open < TSL` 或 `Entry Open < PSAR` 或 `Entry Open > TP` |
| **做空** | `Entry Open > SL` 或 `Entry Open > TSL` 或 `Entry Open > PSAR` 或 `Entry Open < TP` |

### 6.4 代码位置

```
src/backtest_engine/backtester/state/
├── position_calculator.rs        # 进场时调用 init_entry_with_safety_check()
└── risk_trigger/
    ├── gap_check.rs              # init_entry_with_safety_check() 实现
    ├── risk_price_calc.rs        # 风控价格计算公式 (calc_sl_pct_price, get_sl_anchor 等)
    ├── risk_state.rs             # RiskState 结构体定义
    ├── trigger_price_utils.rs    # 触发价格工具函数
    ├── tsl_psar.rs               # PSAR 算法 (init_tsl_psar, update_tsl_psar)
    ├── mod.rs                    # 模块导出
    └── risk_check/               # 风控检查子目录
        ├── mod.rs                # check_risk_exit() 主入口
        ├── trigger_checker.rs    # 触发检测逻辑
        ├── threshold_updater.rs  # update_tsl_thresholds() TSL 阈值更新
        └── outcome_applier.rs    # 触发结果应用
```

**调用流程**:
```rust
// position_calculator.rs
if self.can_entry_long() && self.prev_bar.entry_long {
    let is_safe = self.init_entry_with_safety_check(params, Direction::Long);
    if is_safe {
        self.action.entry_long_price = Some(self.current_bar.open);
        self.action.first_entry_side = 1;
    }
}
```

### 6.5 与 backtesting.py 的对比

| 行为 | pyo3-quant | backtesting.py |
|------|------------|----------------|
| 跳空触发止损 | **跳过进场** | 进场后立即止损 |
| 结果差异 | 无该笔交易 | 有一笔亏损交易 |
| 适用场景 | 更保守 | 更激进 |

> [!NOTE]
> 如果使用无跳空的数据（如 1H/4H 等低频数据），两者的结果可以保持一致。
