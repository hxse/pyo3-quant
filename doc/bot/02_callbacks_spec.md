# 回调函数接口与错误处理规范

本文档详述交易机器人（Bot）与外部系统交互的回调函数接口、数据结构、错误处理机制以及信号定义。

> [!NOTE]
> 本文档是 [01_bot_design_spec.md](./01_bot_design_spec.md) 的补充文档。
>
> **设计原则详见主文档**，此处仅关注具体接口规范。

---

## 1. 接口设计要点

> [!IMPORTANT]
> **API 接口与业务逻辑分离设计**：
> 1. 所有交易所 API 交互都不在 `Bot` 内部硬编码，而是通过回调函数注入。
> 2. 回测引擎（Backtest Engine）也作为外部依赖，通过 `run_backtest` 回调函数注入。
> 3. 这种设计使得 `Bot` 核心逻辑完全独立于具体的交易所实现和回测策略，**便于测试和替换**。
> 4. **回调函数与后端路由 1:1 对应**：每个回调函数的签名、参数名、返回类型都与后端 API 路由完全一致，实现时可直接透传。

### 1.1 类型与结构

- **类型安全**：所有回调函数的**输入和返回**都必须使用 Pydantic 定义。
- **优先使用 Pydantic**：能用 Pydantic 的地方都优先用，以保证类型安全和项目的健壮性。
- **统一返回结构**：所有回调必须返回 `CallbackResult`。

### 1.2 参数与注入

- **策略参数接口** (`get_strategy_params`) 特殊：返回 `List[StrategyParams]`，语义是“多品种策略条目列表”。
- **硬约束**：列表中不允许出现重复 `symbol`；若同一 symbol 出现多个策略条目，机器人会直接报错并拒绝执行。
- **其他接口**：均为**单个**函数。
- **调用方注入**：调用方在实例化机器人时注入所有回调函数。

---

## 2. 回调函数签名

> [!IMPORTANT]
> **Side 字段映射**：
> 文档中 `SignalAction` 使用 `"long"` / `"short"` 表示**持仓方向**。
> 但实际调用交易所 API (如 `create_limit_order`) 时，回调函数**必须**负责将其映射为 API 要求的 `"buy"` / `"sell"`。
>
> 映射逻辑（单向持仓模式）：
> - 开多 (`long` 进场) -> `buy`
> - 开空 (`short` 进场) -> `sell`
> - 平多 (`long` 离场) -> `sell`
> - 平空 (`short` 离场) -> `buy`

### 2.1 策略与回测

| 回调 | 签名 | 用途 |
|------|------|------|
| `get_strategy_params` | `() → CallbackResult[List[StrategyParams]]` | 返回策略参数（数组形式，每个元素对应一个品种策略条目；不允许同 symbol 重复） |
| `run_backtest` | `(StrategyParams, DataFrame) → CallbackResult[BacktestData]` | 运行回测获取信号 |
| `parse_signal` | `(df: DataFrame, params: StrategyParams, index: int = -1) → CallbackResult[SignalState]` | 解析回测结果，支持指定行索引（默认 -1） |

### 2.2 数据与查询

| 回调 | 签名 | 用途 |
|------|------|------|
| `fetch_market_info` | `(symbol) → CallbackResult[MarketInfoResponse]` | 获取精度（支持 Step Size 或 Decimals）、最小量、合约类型等 |
| `fetch_balance` | `() → CallbackResult[BalanceResponse]` | 查询可用余额（计算下单数量） |
| `fetch_tickers` | `(symbols) → CallbackResult[TickersResponse]` | 获取行情（预留，TODO: 开仓前价格偏离检查） |
| `fetch_ohlcv` | `(StrategyParams) → CallbackResult[DataFrame]` | 获取 K 线数据 |
| `fetch_positions` | `(symbols) → CallbackResult[PositionsResponse]` | 获取持仓信息（不包括限价挂单和止盈止损挂单） |
| `fetch_open_orders` | `(symbol) → CallbackResult[OrdersResponse]` | 获取当前挂单（包括限价挂单和止盈止损挂单，不包括持仓） |

### 2.3 订单执行

> [!NOTE]
> **进场支持两种模式**：`create_limit_order`（限价）或 `create_market_order`（市价）二选一。
> - 用户可以通过配置参数 `entry_order_type` (`"limit"` 或 `"market"`) 来切换模式。
>
> **离场直接用 `close_position`**：该品种默认市价全部平仓离场。

| 回调 | 签名 | 用途 |
|------|------|------|
| `create_limit_order` | `(LimitOrderRequest) → CallbackResult[OrderResponse]` | 限价订单（进场） |
| `create_market_order` | `(MarketOrderRequest) → CallbackResult[OrderResponse]` | 市价订单（进场） |
| `create_stop_market_order` | `(StopMarketOrderRequest) → CallbackResult[OrderResponse]` | 挂止损单 |
| `create_take_profit_market_order` | `(TakeProfitMarketOrderRequest) → CallbackResult[OrderResponse]` | 挂止盈单 |

### 2.4 订单管理

| 回调 | 签名 | 用途 |
|------|------|------|
| `close_position` | `(symbol: str, side: Optional[str] = None) → CallbackResult[ClosePositionResponse]` | 关闭指定品种的当前仓位（不包含限价挂单和止盈止损挂单）。`side`: 默认为 `None`（平所有方向），本项目中保持 `side=None`，因为单仓位策略无需区分方向。 |
| `cancel_all_orders` | `(symbol) → CallbackResult[CancelAllOrdersResponse]` | 取消所有挂单（清理孤儿订单） |

### 2.5 不再需要的回调

| 回调 | 原因 |
|------|------|
| ~~`fetch_order`~~ | Kraken 不支持，改用 `fetch_positions` 判断成交 |

---

## 3. 错误处理机制

> [!NOTE]
> 回调函数中可能涉及网络请求，**超时、错误处理、重试逻辑、通知逻辑（如 Telegram Bot, email等）均由用户在回调函数中自定义**。
>
> 这样设计的原因：
> - 不同交易所的错误类型和重试策略不同
> - 用户可根据自身需求定制错误处理和通知逻辑
> - 保持交易机器人核心逻辑简单

### 3.1 统一返回结构

所有回调函数**必须**返回统一的 `CallbackResult` 结构：

```python
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class CallbackResult(BaseModel, Generic[T]):
    """统一的回调函数返回结构"""
    success: bool  # 是否成功
    data: Optional[T] = None  # 成功时返回的数据
    message: Optional[str] = None  # 附加信息（成功或失败都可填写）
```

**泛型类型约定示例**：

```python
create_market_order: Callable[[MarketOrderRequest], CallbackResult[OrderResponse]]
run_backtest: Callable[[StrategyParams, Any], CallbackResult[BacktestData]]
cancel_all_orders: Callable[[str], CallbackResult[CancelAllOrdersResponse]]
```

这样设计的好处：IDE 有完整的类型提示，静态检查（如 `ty check`）能发现类型错误。

### 3.2 职责划分

**用户职责**（在回调函数内部）：
- 自行捕获异常（try/except）
- 自行决定重试策略、通知策略（如 Telegram Bot）
- 根据业务逻辑返回 `success=True` 或 `success=False`

**程序职责**（Bot 核心逻辑）：
- 根据 `success` 决定后续控制流
- `success=False` 时：**记录错误日志，并立即结束本轮循环**（Fail-Fast）
- `success=True` 时：继续执行

### 3.3 控制流规则 (Fail-Fast)

> [!IMPORTANT]
> **全流程 Fail-Fast 原则**
>
> 为保证交易状态的确定性和安全性，交易机器人采用 **Fail-Fast（快速失败）** 策略：
>
> **任意回调函数**（无论是数据获取、回测、还是订单执行）返回 `success=False` 或抛出异常时：
> 1. 立即记录 `ERROR` 级别日志（包含错误信息）。
> 2. **立即终止本轮循环**，不再执行后续任何操作。
> 3. 等待下一秒循环重新开始。
>
> **设计考量**：
> - **安全性优先**：如果 `fetch_positions` 失败，Bot 无法确定当前持仓，强行继续可能导致重复开仓。
> - **逻辑简化**：不再维护复杂的"部分失败依然执行"的逻辑表。
> - **用户掌控**：用户应在回调函数内部处理重试（Retry）和通知（Alert）。一旦错误传播到 Bot，即视为不可恢复的本轮失败。

**执行顺序规则**：

> [!IMPORTANT]
> **严格遵守解析器顺序**
> 交易机器人**必须严格遵守**解析器返回的 `SignalState.actions` 列表顺序依次执行。
>
> 结合 Fail-Fast 原则，这意味着：一旦列表中某个 Action 执行失败，**后续所有 Action（包括 SL/TP）都会被放弃**，直到下一轮循环重新尝试。

### 3.4 日志打印规则

| 日志级别 | 成功时 | 失败时 |
|---------|-------|-------|
| `DEBUG` | 打印 | 打印 |
| `INFO` | 不打印 | 打印 |
| `WARNING` | 不打印 | 打印 |
| `ERROR` | 不打印 | 打印 |

---

## 4. 策略参数与验证

为实现静态验证，`StrategyParams` **必须** 是一个严格定义的 Pydantic 模型（或包含校验逻辑的数据类）。

### 4.1 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `base_data_key` | `str` | 基准周期，如 `"ohlcv_15m"` |
| `symbol` | `str` | 标的品种 |
| `sl_exit_in_bar` | `bool` | 是否使用 SL In-Bar 模式，默认 `True` |
| `tp_exit_in_bar` | `bool` | 是否使用 TP In-Bar 模式，默认 `False` |

### 4.2 验证机制

**静态检查**：
通过回调函数签名 `List[Callable[[], CallbackResult[StrategyParams]]]`，用户必须返回 `StrategyParams` 实例。IDE 和静态类型检查器（如 mypy/pyright）会自动验证：
1. **必填字段**：如 `base_data_key` 缺失会报错
2. **类型检查**：如 `sl_exit_in_bar` 填了字符串会报错

**运行时验证**：
即使绕过了静态检查，Pydantic 在实例化或数据解析时也会**强制进行运行时验证**。如果数据不符合定义（如字段缺失或类型无法转换），会立即抛出 `ValidationError`，防止脏数据进入系统。

---

## 5. 数据获取与回测流程

回调函数的调用顺序：

```
get_strategy_params() → fetch_ohlcv(params) → run_backtest(params, df) → parse_signal(df, params, index)
```

1. 根据策略参数回调获取配置
2. 调用数据回调获取 OHLCV
3. 调用回测引擎回调获取完整结果 DataFrame
4. 调用信号解析回调（传入 DataFrame、StrategyParams 和 index），解析得到 `SignalState`

---

## 6. 信号解析与数据结构

### 6.1 信号解析回调

`parse_signal` 回调用于将回测引擎返回的 **DataFrame** 解析为结构化的 `SignalState`。

> [!TIP]
> **性能优化**：建议直接将整个 Polars DataFrame 传递给 Rust 工具函数。
> `pyo3-polars` 支持 **Zero-copy** 传递 DataFrame 引用。Rust 函数内部直接通过索引读取最后一行数据。

> [!IMPORTANT]
> **职责边界**：
> - **解析器**：纯计算、无状态，只根据 DataFrame 输出**交易意图**，不关心当前仓位/余额/挂单
> - **交易机器人**：负责**运行时检查**（孤儿订单检查、重复开仓检查、最小订单检查）和**动态计算**（下单数量 amount）
>
> 详细说明：
> - 解析逻辑细节请参考 [03_parser_spec.md](./03_parser_spec.md)
> - 运行时检查与动态计算细节请参考 [04_runtime_checks_spec.md](./04_runtime_checks_spec.md)

**实现方式**（用户可选）：
1. **调用 Rust 工具函数**（推荐）：使用 pyo3 暴露的 `parse_signal(df, params, index)` 函数
2. **手动解析**：用户自行提取最后一行并解析

### 6.2 SignalState 定义

```python
from typing import List, Optional, Literal
from pydantic import BaseModel
import polars as pl

# 回调签名：(df: pl.DataFrame, params: StrategyParams, index: int = -1) -> CallbackResult[SignalState]
```

```python
class SignalAction(BaseModel):
    """单个交易意图（Bot 会在执行前做运行时检查）"""
    action_type: Literal[
        "close_position",                    # 平仓
        "create_limit_order",                # 限价进场
        "create_market_order",               # 市价进场
        "create_stop_market_order",          # 挂止损单
        "create_take_profit_market_order",   # 挂止盈单
        "cancel_all_orders"                  # 取消所有挂单
    ]
    symbol: str
    side: Optional[Literal["long", "short"]] = None
    price: Optional[float] = None  # 进场/止损/止盈价格


class SignalState(BaseModel):
    """解析器返回的交易意图（不是完整执行指令）"""
    actions: List[SignalAction]  # 意图列表，Bot 执行前会做运行时检查
    has_exit: bool = False  # 本行是否有任意离场（用于 Bot 判断孤儿检查）
```

### 6.3 side 字段要求

| 动作 | side 字段 |
|------|----------|
| `close_position` | `Optional`，保持 `None`（单仓位策略平所有仓） |
| `cancel_all_orders` | **无** side 字段 |
| `create_limit_order` | **必填** `"long"` 或 `"short"` |
| `create_market_order` | **必填** `"long"` 或 `"short"` |
| `create_stop_market_order` | **必填** `"long"` 或 `"short"` |
| `create_take_profit_market_order` | **必填** `"long"` 或 `"short"` |
