# 回测引擎架构文档

## 系统概述

### 基本特性

这是一个**价格驱动**的量化回测引擎，具有以下核心特征：

- **单仓位系统**: 同一时刻只持有一个方向的仓位（多头或空头）
- **无杠杆交易**: 不支持杠杆，每次使用全部可用资金开仓
- **全仓模式**: 每次开仓都使用当前的全部余额
- **价格驱动状态**: 通过价格字段组合推断状态，而非显式状态枚举
- **双模式风控**: 支持next_bar（下根K线开盘）和in_bar（当根K线内）两种执行模式

### 技术栈

- **核心语言**: Rust（高性能计算）
- **Python绑定**: PyO3（提供Python接口）
- **数据处理**: Polars（高效DataFrame操作）

---

## 输入与输出

### 输入数据

回测引擎需要以下输入：

#### 1. 市场数据（OHLCV）
```python
{
    "time": Vec<i64>,        # 时间戳（毫秒）
    "open": Vec<f64>,        # 开盘价
    "high": Vec<f64>,        # 最高价
    "low": Vec<f64>,         # 最低价  
    "close": Vec<f64>,       # 收盘价
    "volume": Vec<f64>,      # 成交量
    "atr": Option<Vec<f64>>  # ATR指标（可选，用于ATR类风控）
}
```

#### 2. 策略信号
```python
{
    "enter_long": Vec<i32>,   # 多头进场信号
    "exit_long": Vec<i32>,    # 多头离场信号
    "enter_short": Vec<i32>,  # 空头进场信号
    "exit_short": Vec<i32>    # 空头离场信号
}
```

#### 3. 回测参数
```python
{
    "initial_capital": f64,      # 初始资金
    "fee_pct": f64,             # 百分比手续费
    "fee_fixed": f64,           # 固定手续费
    "exit_in_bar": bool,        # 风控是否在当根K线内执行
    
    # 风控参数（可选）
    "sl_pct": f64,              # 百分比止损
    "tp_pct": f64,              # 百分比止盈
    "tsl_pct": f64,             # 百分比跟踪止损
    "sl_atr": f64,              # ATR止损倍数
    "tp_atr": f64,              # ATR止盈倍数
    "tsl_atr": f64              # ATR跟踪止损倍数
}
```

### 输出数据

回测引擎输出一个Polars DataFrame，包含以下列：

#### 价格状态列（核心）
- `entry_long_price`: 多头进场价格
- `entry_short_price`: 空头进场价格
- `exit_long_price`: 多头离场价格
- `exit_short_price`: 空头离场价格

#### 资金状态列
- `balance`: 账户余额（已实现盈亏）
- `equity`: 账户净值（含未实现盈亏）
- `peak_equity`: 历史最高净值
- `trade_pnl_pct`: 单笔回报率
- `total_return_pct`: 累计回报率
- `fee`: 单笔手续费
- `fee_cum`: 累计手续费

#### 风控状态列
- `risk_exit_long_price`: 风控触发的多头离场价格
- `risk_exit_short_price`: 风控触发的空头离场价格
- `risk_exit_in_bar`: 是否在当根K线内触发风控离场 (bool)

#### 风控价格列（可选，用于调试）
- `sl_pct_price`: 百分比止损价格
- `tp_pct_price`: 百分比止盈价格
- `tsl_pct_price`: 百分比跟踪止损价格
- `sl_atr_price`: ATR止损价格
- `tp_atr_price`: ATR止盈价格
- `tsl_atr_price`: ATR跟踪止损价格

---

## 核心架构：价格驱动状态机

### 设计理念

传统回测引擎使用显式的状态枚举（如`Position::Long`, `Position::Short`），而本引擎采用**价格驱动**设计：

> **状态不是存储的，而是从价格组合中推断出来的**

这种设计的优势：
1. **数据即状态**: 价格字段本身就是完整的状态描述
2. **易于调试**: 直接查看价格列即可理解状态流转
3. **简化逻辑**: 避免状态枚举与价格的同步问题

### 状态判断逻辑

状态判断主要依赖 `Action` 结构体中的价格字段：

```rust
pub struct Action {
    // 价格字段（状态机变量，默认延续）
    pub entry_long_price: Option<f64>,
    pub entry_short_price: Option<f64>,
    pub exit_long_price: Option<f64>,
    pub exit_short_price: Option<f64>,

    // 状态标志（辅助判断）
    pub is_first_entry_long: bool,  // 是否多头首次进场
    pub is_first_entry_short: bool, // 是否空头首次进场
}
```

### 状态映射表

| entry_long | exit_long | entry_short | exit_short | risk_in_bar | 状态描述 |
|-----------|-----------|-------------|------------|-------------|---------|
| None | None | None | None | 0 | 无仓位 |
| Some | None | None | None | 0 | 持有多头 |
| None | None | Some | None | 0 | 持有空头 |
| Some | Some | None | None | 0 | 多头离场（策略信号） |
| Some | Some | None | None | 1 | 多头离场（风控触发） |
| None | None | Some | Some | 0 | 空头离场（策略信号） |
| None | None | Some | Some | -1 | 空头离场（风控触发） |
| Some | Some | Some | None | 0 | 反手：平多进空 |
| Some | None | Some | Some | 0 | 反手：平空进多 |

### 状态判断辅助函数

```python
# 伪代码示例（实际用Rust实现）

def has_no_position(state):
    """是否无仓位"""
    return (state.entry_long_price is None and 
            state.entry_short_price is None)

def has_long_position(state):
    """是否持有多头"""
    return (state.entry_long_price is not None and 
            state.exit_long_price is None)

def has_short_position(state):
    """是否持有空头"""
    return (state.entry_short_price is not None and 
            state.exit_short_price is None)

def is_exiting_long(state):
    """是否正在离场多头"""
    return (state.entry_long_price is not None and 
            state.exit_long_price is not None)

def can_enter_long(state):
    """是否可以进入多头（含反手）"""
    return has_no_position(state) or is_exiting_short(state)
```

---

## 信号预处理 (Signal Preprocessing)

在主循环执行前，引擎会使用 Polars Lazy API 对原始信号进行预处理，以解决冲突和过滤无效信号。

### 处理逻辑
1. **冲突解决**:
   - `enter_long` vs `enter_short`: 同时出现时，优先保留 `enter_long`（或根据配置）。
   - `enter` vs `exit`: 同一方向的进出场信号同时出现时，通常优先处理离场或根据逻辑屏蔽。
2. **信号屏蔽**:
   - `skip_mask`: 如果存在跳过掩码（如回撤控制触发），则屏蔽进场信号。
   - `ATR无效`: 如果启用了ATR风控但ATR值为NaN，则屏蔽进场信号。

---

## 主循环逻辑

### 伪代码实现

```python
def backtest_main_loop(prepared_data, params):
    """回测主循环"""
    
    # 初始化状态
    state = BacktestState.new(params)
    results = OutputBuffers.new()
    
    # 遍历每根K线
    for i in range(len(prepared_data)):
        # 更新当前和前一根K线数据
        state.current_bar = prepared_data.get(i)
        state.prev_bar = prepared_data.get(i-1)
        
        # === 阶段1: 仓位计算 (Position Calculation) ===
        # 根据上一根K线的信号和当前价格，计算进出场
        state.calculate_position(params)
        
        # 内部逻辑：
        # 1. 检查是否可以进场（无仓位或反手）
        # 2. 检查是否需要离场（策略信号）
        # 3. 检查风控触发（Risk Trigger）
        
        # === 阶段2: 资金结算 (Capital Calculation) ===
        state.calculate_capital(params)
        
        # === 阶段3: 记录结果 ===
        update_buffer_row(results, state, i)
    
    return results
```

### 首次进场标记 (First Entry Flag)

为了正确初始化风控参数（如设置初始止损价），引擎引入了 `is_first_entry_long` 和 `is_first_entry_short` 标志。

- **设置时机**: 当 `calculate_position` 检测到新的进场动作时，将对应标志设为 `true`。
- **作用**: `RiskState` 在检测到 `is_first_entry` 为 `true` 时，会根据进场价计算并记录初始的 SL/TP/TSL 价格。
- **重置**: 在每根K线处理开始时，标志默认重置为 `false`，只有在当根K线发生进场时才会被置位。

---

## 风控系统

### 触发机制

风控检查在 `calculate_position` 阶段执行。如果触发风控：

1. **设置离场价格**: 更新 `risk_state.exit_long_price` 或 `risk_state.exit_short_price`。
2. **设置离场标记**: 更新 `risk_state.exit_in_bar` 为 `true`。
3. **更新 Action**: 将风控离场价格同步到 `state.action.exit_long_price` 或 `state.action.exit_short_price`。

### 支持的风控类型

1. **百分比止损/止盈** (SL/TP PCT)
2. **ATR止损/止盈** (SL/TP ATR)
3. **跟踪止损** (TSL)

---

## 资金结算机制

### 两轮结算顺序

为了正确处理复杂场景（如反手+风控），资金结算逻辑能够处理同一根K线内的多次状态变更（虽然当前简化版本主要处理单次变更，但架构支持扩展）。

1. **策略离场结算**: 处理基于 `prev_bar` 信号的离场（Next Bar Open）。
2. **风控离场结算**: 处理基于 `current_bar` 价格触发的风控离场（In Bar）。

### 手续费模型

手续费在**离场时**一次性结算，支持百分比手续费和固定手续费。

---

## 性能优化

### 向量化与内存管理

1. **预分配缓冲区**: `OutputBuffers` 在循环前预分配所有 `Vec<f64>`。
2. **PreparedData**: 将 Polars DataFrame 列转换为切片 (`&[f64]`, `&[i32]`)，避免循环中的 DataFrame 索引开销。
3. **Lazy API**: 信号预处理使用 Polars Lazy API，利用其查询优化引擎。

---

## 总结

本回测引擎经过重构，增强了信号处理的健壮性和风控系统的灵活性：

✅ **信号预处理**: 统一处理信号冲突和过滤。
✅ **精确风控**: 引入首次进场标记，确保风控参数正确初始化。
✅ **透明状态**: 输出包含详细的 Risk 状态，便于调试和验证。
✅ **高性能**: 保持了 Rust 核心的高效执行。
