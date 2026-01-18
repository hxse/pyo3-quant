# 回测引擎事件驱动重构计划

## 背景

当前状态机实现存在以下问题：
1. **状态分散**：状态字段分布在 `Action`、`RiskState`、`CapitalState` 多个结构体
2. **修改点分散**：同一状态可能在多处被修改，难以追踪
3. **重置易遗漏**：如 `first_entry_side` 未在 `reset_position_on_skip` 中重置的 Bug

## 设计方案：枚举事件 + ArrayVec

### 核心思想

1. **所有状态变更必须通过事件**：禁止直接 `state.xxx = yyy`
2. **事件集中处理**：单一 `apply` 函数的 `match` 分支
3. **零堆分配**：使用 `ArrayVec<TradeEvent, 16>` 栈分配

### 事件定义

```rust
enum TradeEvent {
    // === 帧开始 ===
    FrameStart,
    BarSkipped { reason: SkipReason },

    // === 仓位重置 ===
    ResetLongPosition,
    ResetShortPosition,

    // === 进出场 ===
    EntryLong { price: f64 },
    EntryShort { price: f64 },
    ExitLong { price: f64, reason: ExitReason },
    ExitShort { price: f64, reason: ExitReason },

    // === 风控 ===
    RiskTriggered { direction: Direction, price: f64, in_bar: bool },
    UpdateRiskThreshold { direction: Direction, thresholds: RiskThresholds },

    // === 资金 ===
    CapitalSettled { balance_delta: f64, fee: f64 },
    EquityUpdated { equity: f64, drawdown: f64 },
}
```

### 主循环结构

```rust
for bar in bars {
    // 1. 业务逻辑只读状态，返回事件列表
    let events = decide(&state, &bar, &prev_bar, params);

    // 2. 集中应用事件
    for event in events {
        apply(&mut state, event);
    }

    // 3. 写入输出
    output.write(&state);

    prev_bar = bar;
}
```

### 关键约束

| 约束 | 实现方式 |
|------|----------|
| 业务逻辑不能直接改状态 | `decide(&State)` 签名只读 |
| 所有重置集中处理 | `FrameStart` 事件的 match 分支 |
| 事件顺序可控 | `apply` 按固定顺序处理 |

---

## 完整事件清单

### Position 事件 (12)

| 事件 | 触发条件 | 修改的状态 |
|------|---------|-----------|
| ResetLongPosition | 上帧 exit_long 存在 | entry_long, exit_long, risk_long_* |
| ResetShortPosition | 上帧 exit_short 存在 | entry_short, exit_short, risk_short_* |
| ExitLongSignal | 持多 + 信号 | exit_long_price |
| ExitShortSignal | 持空 + 信号 | exit_short_price |
| ResetFirstEntrySide | 每帧 | first_entry_side=0 |
| EntryLong | 可进多 + 信号 | entry_long_price, first_entry_side=1 |
| EntryShort | 可进空 + 信号 | entry_short_price, first_entry_side=-1 |
| InitRiskThresholds | 进场时 gap_check | sl_*, tp_*, tsl_*, anchor_* (初始化) |
| ResetRiskExitState | 每帧 | risk_*_price, in_bar_direction |
| RiskExitLongInBar | 风控触发 | exit_long_price, in_bar_direction |
| RiskExitShortInBar | 风控触发 | exit_short_price, in_bar_direction |
| BarSkipped | balance<=0 | 全部重置 |

### Capital 事件 (4)

| 事件 | 修改的状态 |
|------|-----------|
| ResetBarCapital | fee, trade_pnl_pct |
| ExitLongPnl | balance, fee, fee_cum |
| ExitShortPnl | balance, fee, fee_cum |
| UpdateEquity | equity, peak_equity, drawdown, total_return_pct |

### Risk Threshold 事件 (4)

| 事件 | 修改的状态 |
|------|-----------|
| UpdateSlPrice | sl_pct_price_*, sl_atr_price_* |
| UpdateTpPrice | tp_pct_price_*, tp_atr_price_* |
| UpdateTslPrice | tsl_*_price_*, anchor_since_entry |
| UpdatePsarState | tsl_psar_state_*, tsl_psar_price_* |

**总计：20 种事件，单帧最多 ~10 个**

---

## 位掩码编码 + PyO3 暴露

### 设计思路

1. 每帧事件编码为 `u32` 位掩码，存入 `Vec<u32>` 输出到 DataFrame
2. Rust 提供工具方法：`events_to_bitmask()` / `bitmask_to_events()`
3. 通过 PyO3 暴露给 Python，pytest 可以用位运算断言

### Rust 侧

```rust
// 事件位定义
pub mod event_bits {
    pub const FRAME_START: u32      = 1 << 0;
    pub const ENTRY_LONG: u32       = 1 << 1;
    pub const ENTRY_SHORT: u32      = 1 << 2;
    pub const EXIT_LONG: u32        = 1 << 3;
    pub const EXIT_SHORT: u32       = 1 << 4;
    pub const RISK_LONG_INBAR: u32  = 1 << 5;
    pub const RISK_SHORT_INBAR: u32 = 1 << 6;
    pub const BAR_SKIPPED: u32      = 1 << 7;
    // ... 最多 32 种
}

// 编码
fn events_to_bitmask(events: &[TradeEvent]) -> u32 {
    let mut mask = 0u32;
    for e in events {
        mask |= match e {
            TradeEvent::FrameStart => event_bits::FRAME_START,
            TradeEvent::EntryLong { .. } => event_bits::ENTRY_LONG,
            // ...
        };
    }
    mask
}

// 解码（用于调试）
#[pyfunction]
fn bitmask_to_event_names(mask: u32) -> Vec<String> {
    let mut names = vec![];
    if mask & event_bits::ENTRY_LONG != 0 { names.push("EntryLong".into()); }
    if mask & event_bits::EXIT_LONG != 0 { names.push("ExitLong".into()); }
    // ...
    names
}
```

### Python 侧

#### 类型定义 (py_entry/types/events.py)

```python
from pydantic import BaseModel
from enum import StrEnum
from pyo3_quant import bitmask_to_event_names as _bitmask_to_names

class EventType(StrEnum):
    """事件类型枚举，与 Rust TradeEvent 保持一致"""
    FrameStart = "FrameStart"
    EntryLong = "EntryLong"
    EntryShort = "EntryShort"
    ExitLong = "ExitLong"
    ExitShort = "ExitShort"
    RiskLongInBar = "RiskLongInBar"
    RiskShortInBar = "RiskShortInBar"
    BarSkipped = "BarSkipped"
    ResetLongPosition = "ResetLongPosition"
    ResetShortPosition = "ResetShortPosition"
    # ... 与 Rust 侧保持同步

def bitmask_to_events(mask: int) -> set[EventType]:
    """将位掩码转换为 EventType 集合"""
    return {EventType(name) for name in _bitmask_to_names(mask)}
```

#### 测试用例 (pytest)

```python
from py_entry.types.events import EventType, bitmask_to_events

def test_entry_then_risk_exit():
    df = run_backtest(...)
    events = bitmask_to_events(df["frame_events"][100])

    assert EventType.EntryLong in events
    assert EventType.RiskLongInBar in events
    assert EventType.ExitLong not in events

def test_no_entry_on_skip():
    df = run_backtest(...)
    events = bitmask_to_events(df["frame_events"][100])

    assert EventType.BarSkipped in events
    assert EventType.EntryLong not in events
```

### 优势

| 特性 | 说明 |
|------|------|
| **零字符串** | 纯数值，无序列化开销 |
| **紧凑存储** | 每帧 4 字节 |
| **跨语言** | Rust/Python 共用同一套位定义 |
| **可调试** | `bitmask_to_event_names()` 可读输出 |

---

## TODO

- [ ] 定义 `TradeEvent` 枚举
- [ ] 定义 `event_bits` 模块（位掩码常量）
- [ ] 实现 `events_to_bitmask()` 编码函数
- [ ] 实现 `bitmask_to_event_names()` 解码函数
- [ ] 通过 PyO3 暴露 `event_bits` 和 `bitmask_to_event_names`
- [ ] 实现 `apply(&mut State, TradeEvent)` 函数
- [ ] 重构 `calculate_position` → `decide_position(&State) -> Events`
- [ ] 重构 `calculate_capital` → `decide_capital(&State) -> Events`
- [ ] 重构 `check_risk_exit` → `decide_risk(&State) -> Events`
- [ ] 修改 `main_loop.rs` 为事件驱动模式
- [ ] 在输出 DataFrame 中添加 `frame_events` 列
- [ ] 删除所有分散的 `reset_*` 函数
- [ ] 更新 pytest 测试用例（使用位掩码断言）
- [ ] 更新架构文档
