# 单仓位回测状态机：约束与状态推断

本文档详细描述**单仓位回测引擎**状态机的核心设计原理。

## 系统特性

- **单仓位系统**：同一时刻只能持有一个方向的仓位（多头或空头），不支持同时持有多空
- **全仓模式**：每次开仓使用全部可用资金，无杠杆
- **价格驱动状态**：不使用显式 Position 枚举，而是通过价格字段组合推断状态

---

## 核心命题

> **数据清洗约束 + 运行时逻辑约束 = 可严格推断单 Bar 内所有仓位状态**

---

## 1. 术语区分

> ⚠️ **重要**：信号与价格是两个不同层次的概念，必须区分清楚。

| 层次 | 字段 | 类型 | 来源 |
|------|------|------|------|
| **信号层** | `entry_long`, `exit_long` | `bool` | 策略生成，经预处理清洗 |
| **价格层** | `entry_long_price`, `exit_long_price` | `Option<f64>` | 运行时根据信号+约束计算 |

- 信号是"意图"：策略**想要**做什么
- 价格是"结果"：引擎**实际执行**了什么

状态枚举基于**价格层**而非信号层。

---

## 2. 约束体系

### 2.1 数据清洗约束（预处理阶段）

在主循环执行前，通过 Polars Lazy API 对**信号**进行清洗。

| 规则 | 条件 | 处理 | 目的 |
|-----|------|------|------|
| R1 | `entry_long ∧ entry_short` | 两者都设为 `false` | 禁止同时进入多空 |
| R2 | `entry_long ∧ exit_long` | `entry_long = false` | 禁止进多同时平多 |
| R3 | `entry_short ∧ exit_short` | `entry_short = false` | 禁止进空同时平空 |
| R4 | `skip_mask = true` | 进场信号屏蔽 | 回撤暂停 |
| R5 | `atr = NaN` | 进场信号屏蔽 | ATR 无效保护 |

**输出保证**（以下信号组合被**拒绝**，不会出现）：
```
❌ entry_long ∧ entry_short   // 被 R1 拒绝
❌ entry_long ∧ exit_long     // 被 R2 拒绝
❌ entry_short ∧ exit_short   // 被 R3 拒绝
```

---

### 2.2 运行时逻辑约束（主循环阶段）

在 `BacktestState::calculate_position()` 中，代码逻辑隐含以下约束：

| 约束 | 相关方法/逻辑 | 效果 |
|------|-----------------|------|
| **价格重置** | `reset_long_state()` / `reset_short_state()` | 上一 bar 离场后重置对应方向价格，确保离场后可进入新仓位 |
| **进场需无仓位或反手** | `can_entry_long() = has_no_position() \|\| is_exiting_short()` | 禁止加仓、禁止同时持有多空 |
| **离场需持仓** | `has_long_position()` 时才设置 `exit_long_price` | 禁止对不存在的仓位离场 |
| **风控离场覆盖策略离场** | `!should_exit_in_bar_long()` 条件 | in_bar 已平仓则不再 next_bar 平仓 |
| **风控需持仓** | `check_risk_exit()` 仅在 `has_long_position()` 时调用 | 无仓位不触发风控 |

**推论**：
- `exit_long_price` 存在 → `entry_long_price` 必存在
- `exit_short_price` 存在 → `entry_short_price` 必存在
- 不可能同时持有多空仓位
- 持仓时忽略同向进场信号
- 无仓时忽略离场信号

### 2.3 执行顺序（关键设计）

> [!IMPORTANT]
> 同 bar 最复杂的场景是：先平仓（开盘价）→ 再反手开仓（开盘价）→ 再触发风控离场（SL/TP 价）
>
> 因此执行顺序必须是：**先离场 → 后进场 → 最后 risk**

```
1. 价格重置（上一 bar 离场完成后清理）
2. 策略离场检查（设置 exit_price）
3. 策略进场检查（此时 is_exiting_*() 可正确返回 true，支持反手）
4. Risk 离场检查（对新开仓位进行风控）
```

**为什么这个顺序是正确的**：

| 步骤 | 价格 | 说明 |
|------|------|------|
| 策略离场 | 开盘价 | 平掉上一根 K 线信号的仓位 |
| 策略进场 | 开盘价 | 按上一根 K 线信号反手开仓 |
| Risk 离场 | SL/TP 价 | 对新开仓位进行 in_bar 风控 |

这个顺序确保了 `can_entry_long()` 检查 `is_exiting_short()` 时，`exit_short_price` 已经被设置，从而正确触发反手逻辑。

---

## 3. 状态推断

### 3.1 有效状态白名单

回测状态采用 **"15 + 2"** 推断模式工作：
1. 基于**六个字段**（四个价格 + `in_bar_direction` + `first_entry_side`）组合推断出 **15 种** 通用持仓状态。
2. 引入 **2 种** 特殊状态：
   - `GapBlocked`: 标记因跳空保护而被拦截的进场信号。在价格表现上等价于 `no_position`（全为 NaN），但语义上表示"本该进场但被拦截"。
   - `CapitalExhausted`: 标记因资金耗尽而停止交易的状态。在价格表现上等价于 `no_position`（全为 NaN），但语义上表示"因破产而强制停止"。

> ⚠️ **白名单机制**：状态枚举表是**允许列表**，不在列表中的组合均为非法状态。

| # | entry_L | exit_L | entry_S | exit_S | in_bar | first_entry | gap_blocked | 状态 |
|:-:|:-------:|:------:|:-------:|:------:|:------:|:-----------:|:-----------:|------|
| 1 | ✗ | ✗ | ✗ | ✗ | 0 | 0 | ✗ | `no_position` |
| 2 | ✓ | ✗ | ✗ | ✗ | 0 | 0 | ✗ | `hold_long` (延续) |
| 3 | ✓ | ✗ | ✗ | ✗ | 0 | 1 | ✗ | `hold_long_first` (进场) |
| 4 | ✗ | ✗ | ✓ | ✗ | 0 | 0 | ✗ | `hold_short` (延续) |
| 5 | ✗ | ✗ | ✓ | ✗ | 0 | -1 | ✗ | `hold_short_first` (进场) |
| 6 | ✓ | ✓ | ✗ | ✗ | 0 | 0 | ✗ | `exit_long_signal` |
| 7 | ✓ | ✓ | ✗ | ✗ | 1 | 0 | ✗ | `exit_long_risk` (持仓后) |
| 8 | ✓ | ✓ | ✗ | ✗ | 1 | 1 | ✗ | `exit_long_risk_first` (秒杀) |
| 9 | ✗ | ✗ | ✓ | ✓ | 0 | 0 | ✗ | `exit_short_signal` |
| 10| ✗ | ✗ | ✓ | ✓ | -1 | 0 | ✗ | `exit_short_risk` (持仓后) |
| 11| ✗ | ✗ | ✓ | ✓ | -1 | -1 | ✗ | `exit_short_risk_first` (秒杀) |
| 12| ✓ | ✓ | ✓ | ✗ | 0 | -1 | ✗ | `reversal_L_to_S` |
| 13| ✓ | ✗ | ✓ | ✓ | 0 | 1 | ✗ | `reversal_S_to_L` |
| 14| ✓ | ✓ | ✓ | ✓ | 1 | 1 | ✗ | `reversal_to_L_risk` |
| 15| ✓ | ✓ | ✓ | ✓ | -1 | -1 | ✗ | `reversal_to_S_risk` |
| 16| ✗ | ✗ | ✗ | ✗ | 0 | 0 | ✓ | `gap_blocked` |
| 17| ✗ | ✗ | ✗ | ✗ | 0 | 0 | ✗ | `capital_exhausted` |

> **状态说明**：
> - `gap_blocked`: 特殊状态。当信号指示进场但因跳空保护被拦截时触发。由于未成交，其价格字段与 `no_position` 一致（全空），用于区分"无信号"和"信号被拦截"。
> - `capital_exhausted`: 特殊状态。当账户资金归零时触发。由于交易能力丧失，其价格字段与 `no_position` 一致（全空），用于区分"正常空仓"和"因爆仓停止"。
> - `first_entry_side`：标记进场方向。`0`=非进场 bar，`1`=多头首次进场，`-1`=空头首次进场
> - `in_bar_direction`：标记离场模式。`0`=无/Next-Bar 离场，`1`=多头 In-Bar 离场，`-1`=空头 In-Bar 离场
> - "秒杀" 状态：同 bar 内进场后立即被风控平仓（`first_entry_side` 和 `in_bar_direction` 同时非零）

### 3.2 被排除的组合（示例）

以下是部分被约束排除的组合示例。由于组合数量较多，无法完全列举，测试中使用白名单验证。

| 组合 | 排除原因 |
|------|----------|
| `(✓,✗,✓,✗)` | 同时持有多空，违反单仓位约束 |
| `(✗,✓,✗,✗)` | 孤立的 exit_long_price，无对应 entry |
| `(✗,✗,✗,✓)` | 孤立的 exit_short_price，无对应 entry |
| `(✗,✓,✗,✓)` | 两个孤立的 exit，无任何 entry |

---

## 4. 完备性论证

### 4.1 充分性

**给定任意有效的运行时状态，必然可以在白名单中找到唯一匹配。**

### 4.2 必要性

**白名单中的每个状态都是可达的。**

- 状态 1-5：无仓位或持仓状态（no_position、hold_long/short、hold_long/short_first）
- 状态 6-11：离场（策略离场、风控离场、秒杀离场）
- 状态 12-13：反手进场（reversal_L_to_S、reversal_S_to_L）
- 状态 14-15：反手后同 bar 风控离场（reversal_to_L/S_risk）

---

## 5. 设计决策

### 5.1 约束即契约

数据清洗不是可选的"优化"，而是状态机正确运行的**前置契约**。

### 5.2 状态即价格 (Price Driven Inference)

本引擎采用 **"Price Driven Inference" (价格驱动推断)** 的核心设计范式。

> [!IMPORTANT]
> **frame_state 是从 price 推断的，而非反过来。**
>
> 引擎的状态驱动源头是四个价格字段 (`entry/exit_long/short_price`) + `in_bar_direction` + `first_entry_side` + `gap_blocked`。
> `FrameState` 枚举是在 `calculate_position()` 结束后，通过 `FrameState::infer()` 从这些字段**被动推断**出来的只读标签。它仅用于输出和调试，不参与任何业务逻辑决策。

**这一设计的意义**：
1. **Single Source of Truth**：消除了"枚举状态"与"价格数值"不一致的可能性。价格本身就是状态。
2. **零同步成本**：在反手、秒杀等复杂场景下，无需手动维护枚举状态，只需关注价格计算的正确性。
3. **调试透明**：看到价格即可反推状态，看到状态即可印证价格。

**优势**：
- **可审计**：DataFrame 输出即完整状态日志
- **无同步问题**：不存在枚举与价格不一致的 bug
- **调试友好**：直接查看价格列即可理解状态流转
- **测试简单**：只需验证每行状态是否在白名单内即可

### 5.3 `in_bar_direction` 与 `first_entry_side` 的必要性

- **`in_bar_direction`** (i8): 标记**离场**模式。0=Next-Bar, 1=多头In-Bar, -1=空头In-Bar。
- **`first_entry_side`** (i8): 标记**进场**模式。0=无进场, 1=多头进场, -1=空头进场。

**推断逻辑**：
- 用户通过 `exit_long_price` 且 `in_bar_direction == 1` 识别风控离场。
- 用户通过 `entry_long_price` 存在且 `first_entry_side == 1` 识别多头进场 Bar，无需使用 `shift(1)` 比较。
- **“秒杀”场景推断**（即进即出）：
  * 例如（多头）`first_entry_side == 1` 且 `in_bar_direction == 1`，同时 `entry_long_price` 和 `exit_long_price` 均存在时，表示发生了极端风控场景。

---

## 6. 总结

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   原始信号      │ ──▶ │   数据清洗      │ ──▶ │   无冲突信号    │
│  (可能冲突)     │     │  (拒绝非法组合) │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 15 种合法状态   │ ◀── │   价格字段组合  │ ◀── │   运行时约束    │
│   (白名单)      │     │ + in_bar_dir    │     │ (仓位计算逻辑)  │
│                 │     │ + first_entry   │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```


## 7. 测试覆盖

15 种状态均有对应的自动化测试验证其合法性。

### 测试文件

| 文件 | 说明 |
|-----|------|
| [test_state_whitelist.py](file:///home/hxse/pyo3-quant/py_entry/Test/backtest/common_tests/test_state_whitelist.py) | 白名单验证：检测每行状态是否在 15 种合法状态中 |
| [test_price_driven_state.py](file:///home/hxse/pyo3-quant/py_entry/Test/backtest/common_tests/test_price_driven_state.py) | 价格驱动状态推断逻辑测试 |

### 运行测试

```bash
just test py_entry/Test/backtest/common_tests/test_state_whitelist.py
just test py_entry/Test/backtest/common_tests/test_price_driven_state.py
```
