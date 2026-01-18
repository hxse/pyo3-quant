# 交易机器人测试策略

本文档描述如何对交易机器人进行完全离线测试。

> [!NOTE]
> 本文档基于新架构设计，对应 [01_bot_design_spec.md](./01_bot_design_spec.md) 中的无状态、回调驱动架构。

---

## 1. 测试架构概述

### 1.1 为什么容易测试

新架构具有以下特点，使得测试变得非常简单：

| 特点 | 测试优势 |
|------|----------|
| **回调函数驱动** | 所有外部依赖都通过回调注入，可完全 Mock |
| **回调与路由 1:1 对应** | Mock 返回值可直接复用后端 API 的响应结构 |
| **无状态架构** | 不需要持久化/恢复状态，每次测试独立 |
| **职责分离** | 解析器和 Bot 可独立测试 |
| **Fail-Fast** | 错误路径明确，易于验证 |

### 1.2 测试分层

```
┌─────────────────────────────────────────────┐
│            端到端测试 (E2E)                  │
│   完整周期执行，验证整体行为                  │
├─────────────────────────────────────────────┤
│            集成测试                          │
│   多组件协作，如：信号→运行时检查→执行        │
├─────────────────────────────────────────────┤
│            单元测试                          │
│   单个组件：解析器、运行时检查、周期判断       │
└─────────────────────────────────────────────┘
```

---

## 2. Mock 回调函数

由于所有外部交互都通过回调函数，可以通过 **Mock 回调** 实现完全离线测试。

### 2.1 Mock 分层

| 回调类型 | 真实实现 | Mock 实现 |
|---------|---------|-----------|
| **策略参数** | 读取配置 | 返回固定 `StrategyParams` |
| **OHLCV 数据** | 请求后端 API | 返回预生成的 DataFrame |
| **回测引擎** | 调用 Rust 引擎 | 返回预设的回测结果 |
| **账户余额** | 请求后端 API | 返回 `BalanceResponse(free={"USDT": 10000.0})` |
| **市场信息** | 请求后端 API | 返回 `MarketInfoResponse(precision_amount=3, min_amount=0.001)` |
| **持仓查询** | 请求后端 API | 返回 `PositionsResponse` (可控的持仓状态) |
| **订单查询** | 请求后端 API | 返回 `OrdersResponse` (可控的挂单状态) |
| **订单创建** | 请求后端 API | 记录调用参数，返回 `OrderResponse` |
| **平仓/取消** | 请求后端 API | 记录调用参数，返回成功 |

### 2.2 Mock 回调示例

```python
from typing import List, Optional
from pydantic import BaseModel

class MockCallbacks:
    """可配置的 Mock 回调集合"""

    def __init__(self):
        self.call_log: List[dict] = []  # 记录所有回调调用

        # 可配置的返回值
        self.positions: List[PositionStructure] = []
        self.balance: dict = {"USDT": {"free": 10000.0}}
        self.market_info = MarketInfoResponse(
            symbol="BTC/USDT",
            precision_amount=3,
            min_amount=0.001,
            # ...
        )

    def fetch_positions(self, symbols) -> CallbackResult[PositionsResponse]:
        self.call_log.append({"method": "fetch_positions", "args": symbols})
        return CallbackResult(success=True, data=PositionsResponse(positions=self.positions))

    def create_limit_order(self, request: LimitOrderRequest) -> CallbackResult[OrderResponse]:
        self.call_log.append({"method": "create_limit_order", "args": request.model_dump()})
        return CallbackResult(success=True, data=OrderResponse(order=OrderStructure(
            id="mock_order_123",
            status="open",
            symbol=request.symbol,
            # ...
        )))

    # ... 其他回调方法
```

### 2.3 验证调用序列

```python
def test_entry_flow():
    mock = MockCallbacks()
    bot = TradingBot(callbacks=mock)

    # 执行
    bot.run_single_step(signal=entry_signal)

    # 验证调用序列
    assert mock.call_log[0]["method"] == "fetch_positions"  # 重复开仓检查
    assert mock.call_log[1]["method"] == "fetch_balance"    # 获取余额
    assert mock.call_log[2]["method"] == "fetch_market_info"  # 获取精度
    assert mock.call_log[3]["method"] == "create_limit_order"  # 下单
    assert mock.call_log[4]["method"] == "create_stop_market_order"  # 挂 SL
```

---

## 3. 测试类型

### 3.1 单元测试：解析器

测试 `parse_signal` 回调（或 Rust 实现）的输出是否正确。

| 场景 | 输入 | 期望输出 |
|------|------|----------|
| **多头进场** | `first_entry_side=1` | `actions=[create_limit_order(long), create_stop_market_order]` |
| **空头进场** | `first_entry_side=-1` | `actions=[create_limit_order(short), create_stop_market_order]` |
| **多头离场** | `exit_long_price > 0` | `actions=[close_position, cancel_all_orders]` |
| **反手 L→S** | 同一 K 线离多进空 | `actions=[close_position, cancel_all_orders, create_order(short), ...]` |
| **In-Bar SL** | SL 触发 | `actions=[], has_exit=True` |
| **无信号** | `first_entry_side=0` | `actions=[]` |

> 详见 [03_parser_spec.md](./03_parser_spec.md)

### 3.2 单元测试：运行时检查

测试 Bot 内部的检查逻辑。

| 检查 | 场景 | 期望行为 |
|------|------|----------|
| **重复开仓检查** | 信号=开多，持仓=多 | 跳过开仓 |
| **重复开仓检查** | 信号=开多，持仓=空 | 警告并跳过（异常状态） |
| **重复开仓检查** | 信号=开多，持仓=无 | 允许开仓 |
| **孤儿订单检查** | 无持仓，有挂单 | 执行 `cancel_all_orders` |
| **孤儿订单检查** | 有持仓 | 不取消 |
| **最小订单检查** | amount < min_amount | 跳过开仓，记录 WARNING |
| **最小订单检查** | amount ≥ min_amount | 允许开仓 |

> 详见 [04_runtime_checks_spec.md](./04_runtime_checks_spec.md)

### 3.3 单元测试：周期判断

```python
@pytest.mark.parametrize("base_data_key,current_time,expected", [
    ("ohlcv_15m", "2024-01-01T00:00:00Z", True),   # 整点
    ("ohlcv_15m", "2024-01-01T00:15:00Z", True),   # 15分
    ("ohlcv_15m", "2024-01-01T00:07:00Z", False),  # 非周期点
    ("ohlcv_1h", "2024-01-01T01:00:00Z", True),    # 整点
    ("ohlcv_1h", "2024-01-01T00:30:00Z", False),   # 非整点
])
def test_period_check(base_data_key, current_time, expected):
    result = is_new_period(base_data_key, current_time, last_run_time)
    assert result == expected
```

### 3.4 集成测试：完整流程

| 场景 | 测试内容 |
|------|----------|
| **正常进场** | 信号 → 重复开仓检查 → 余额计算 → 限价单 → SL 条件单 |
| **正常离场** | 离场信号 → 平仓 → 取消所有挂单 |
| **反手流程** | 平仓 → 取消挂单 → 开反向 → 挂新 SL/TP |
| **孤儿清理** | 上一根有离场 → 无持仓 → 取消所有挂单 |
| **Fail-Fast** | `fetch_positions` 失败 → 立即终止本轮 |

### 3.5 Fail-Fast 测试

验证任意回调失败时，Bot 正确终止本轮循环。

```python
def test_fail_fast_on_fetch_positions_failure():
    mock = MockCallbacks()
    mock.fetch_positions = lambda _: CallbackResult(success=False, message="Network error")
    bot = TradingBot(callbacks=mock)

    # 执行
    result = bot.run_single_step(signal=entry_signal)

    # 验证
    assert result.success == False
    assert "fetch_positions" in result.message
    assert len([c for c in mock.call_log if c["method"] == "create_limit_order"]) == 0  # 没有下单
```

---

## 4. 性能优化：预计算信号

### 4.1 问题

| 方案 | 100 根 K 线测试耗时 |
|------|---------------------|
| 真实时间（1秒/次） | 100 秒 |
| 0 秒循环 + 每次回测 | 5-7 秒 |
| **预计算信号 + 单步执行** | **< 0.1 秒** |

### 4.2 解决方案

在测试开始时，一次性运行回测引擎计算完整的信号序列。单步执行时，直接通过索引获取对应信号。

**预计算流程**：

1. 准备测试用的 OHLCV 数据（Polars DataFrame）
2. 一次性调用 `run_backtest` 获取完整回测结果
3. 遍历回测结果，对每个时间点调用 `parse_signal` 预计算信号
4. 将信号存入列表，测试时通过索引直接获取

**关键点**：回测结果是 Polars DataFrame，测试代码应尽量使用 **Polars API** 进行数据操作，避免转换为其他格式。`parse_signal(df, params, index)` 通过 `index` 参数指定要解析的行。

### 4.3 单步执行接口

Bot 应提供 `run_single_step` 接口，支持直接传入预计算信号：

```python
def run_single_step(
    self,
    signal: Optional[SignalState] = None,  # 如果提供，跳过回测
    prev_signal: Optional[SignalState] = None,
) -> StepResult:
    ...
```

---

## 5. 时间控制

### 5.1 问题

Bot 依赖系统时间判断周期，测试时需要控制时间。

### 5.2 解决方案：注入时间函数

```python
class TradingBot:
    def __init__(
        self,
        callbacks: Callbacks,
        time_func: Callable[[], datetime] = datetime.utcnow,  # 可注入
    ):
        self.time_func = time_func
```

测试时传入可控的时间函数：

```python
def test_period_progression():
    current_time = datetime(2024, 1, 1, 0, 0, 0)

    def mock_time():
        return current_time

    bot = TradingBot(callbacks=mock, time_func=mock_time)

    # 推进时间
    current_time = datetime(2024, 1, 1, 0, 15, 0)

    # 验证进入新周期
    assert bot.is_new_period() == True
```

---

## 6. 测试覆盖场景清单

### 6.1 信号解析

| 场景 | 描述 |
|------|------|
| 正常多头进场 | `first_entry_side=1` → 生成开多 + SL 动作 |
| 正常空头进场 | `first_entry_side=-1` → 生成开空 + SL 动作 |
| 多头离场 | `exit_long_price > 0` → 生成平仓 + 取消挂单 |
| 空头离场 | `exit_short_price > 0` → 生成平仓 + 取消挂单 |
| 反手 L→S | 同 K 线离多进空 → 平仓 + 取消 + 开空 + SL |
| 反手 S→L | 同 K 线离空进多 → 平仓 + 取消 + 开多 + SL |
| In-Bar SL 触发 | SL 被交易所触发 → `actions=[], has_exit=True` |
| In-Bar TP 触发 | TP 被交易所触发 → `actions=[], has_exit=True` |
| 无信号 | 无进离场 → `actions=[]` |

### 6.2 运行时检查

| 场景 | 描述 |
|------|------|
| 重复开仓-同向 | 已有多仓时再开多 → 跳过 |
| 重复开仓-反向 | 已有多仓时开空信号 → 警告并跳过 |
| 孤儿订单-触发 | 无仓位但有挂单 → 取消 |
| 孤儿订单-不触发 | 有仓位 → 不取消 |
| 最小订单-不足 | amount < min_amount → 跳过开仓 |
| 最小订单-通过 | amount ≥ min_amount → 允许开仓 |
| 下单数量计算 | 余额 × 仓位% × 杠杆 / 价格 → 正确精度 |

### 6.3 错误处理

| 场景 | 描述 |
|------|------|
| fetch_positions 失败 | → 终止本轮，不下单 |
| fetch_balance 失败 | → 终止本轮，不下单 |
| create_limit_order 失败 | → 终止本轮，不挂 SL/TP |
| cancel_all_orders 失败 | → 记录错误，继续执行（非 Fail-Fast） |

### 6.4 周期判断

| 场景 | 描述 |
|------|------|
| 15m 周期-整点 | 00:00, 00:15, 00:30, 00:45 → 触发 |
| 15m 周期-非整点 | 00:07 → 不触发 |
| 1h 周期-整点 | 00:00, 01:00 → 触发 |
| 避免重复执行 | 同一周期内多次检查 → 只执行一次 |

---

### 6.5 日志功能

| 场景 | 描述 |
|------|------|
| log_level=DEBUG | 所有日志（包括成功操作）均输出 |
| log_level=INFO | 只输出关键操作（进场、离场、挂单）和错误 |
| log_level=WARNING | 只输出警告和错误 |
| log_level=ERROR | 只输出错误 |
| 成功操作日志格式 | 包含 symbol、action、price、amount 等关键信息 |
| 失败操作日志格式 | 包含 error message、回调名称、触发时机 |

### 6.6 配置参数

| 参数 | 测试场景 | 描述 |
|------|----------|------|
| `loop_interval_sec` | 设置为 0.5s | 验证循环间隔正确应用 |
| `log_level` | 设置为不同级别 | 验证日志过滤正确（见 6.5） |
| `entry_order_type=limit` | 进场信号 | 调用 `create_limit_order` |
| `entry_order_type=market` | 进场信号 | 调用 `create_market_order` |
| `enable_aggregation=True` | 当前版本 | 应报错或警告（不支持） |
