# API 调用优化（缓存与去重）

本文档描述交易机器人 API 调用的优化设计，旨在减少每个执行周期内对交易所 API 的冗余请求。

> [!NOTE]
> 这是一个**可选**的高级功能，初始版本可以暂不实现，不影响机器人的核心交易逻辑。

---

## 1. 设计前提与理念

### 1.1 设计前提

- 回测引擎是**单品种单策略单仓位**（One Strategy Per Symbol）。
- 交易机器人支持**多品种**，但遵循**每个品种对应唯一策略**的原则。
- **不支持策略聚合和仓位聚合**：每个 Symbol 的交易逻辑和仓位管理是完全独立的。
- 主循环按 Symbol 遍历，每个 Symbol 在同一周期内独立处理。

### 1.2 问题场景

在一个周期循环内，同一个 Symbol 可能因不同逻辑多次调用同一个 API：

- **`fetch_positions`**：
  - 孤儿订单检查（Orphan Check）会调用。
  - 开仓前的重复开仓检查（Checking Duplicate）也会调用。
  - 如果中间没有成交，第二次查询是冗余的。

- **`cancel_all_orders`**：
  - 信号解析器可能生成 `cancel_all_orders` 动作（如反手或离场时）。
  - 孤儿订单检查逻辑也可能触发 `cancel_all_orders`。
  - 如果一秒内连续发送两次取消请求，虽然安全，但浪费 API 权重。

### 1.3 核心规则

优化逻辑遵循以下核心规则：

1. **有副作用则重置**：如果两次调用之间发生了**订单操作**（开仓/平仓/挂单），状态发生改变，缓存必须失效，下次必须重新执行 API 调用。
2. **无副作用则复用**：如果两次调用之间**无订单操作**，则可以：
   - 复用上次 `fetch_positions` 的结果（Cache）。
   - 跳过重复的 `cancel_all_orders` 请求（Deduplication）。

---

## 2. 解决方案：SymbolContext

利用 Python `for` 循环的特性，在每次遍历 Symbol 时创建一个独立的**上下文对象**，无需维护全局状态。

### 2.1 状态对象设计

`SymbolContext` 负责维护单次循环内的缓存和去重标记。

```python
from typing import Optional

class SymbolContext:
    """
    单个 symbol 的执行上下文。
    每个 for 循环迭代创建新实例，循环结束自动销毁。
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._positions_cache: Optional[PositionsResponse] = None
        self._cancelled: bool = False

    # ===== fetch_positions 缓存 =====
    def get_positions_cache(self) -> Optional[PositionsResponse]:
        """获取缓存的持仓数据，如果没有返回 None"""
        return self._positions_cache

    def set_positions_cache(self, data: PositionsResponse):
        """设置持仓缓存"""
        self._positions_cache = data

    # ===== cancel_all_orders 去重 =====
    def is_cancelled(self) -> bool:
        """本周期是否已对该 symbol 执行过取消操作"""
        return self._cancelled

    def mark_cancelled(self):
        """标记已执行过取消"""
        self._cancelled = True

    # ===== 订单操作后调用 =====
    def invalidate(self):
        """
        订单成交类操作（开仓/平仓/挂单）后调用，使状态失效。
        注意：cancel_all_orders 不算订单成交，不需要调用此方法。
        """
        self._positions_cache = None
        self._cancelled = False
```

> [!IMPORTANT]
> **invalidate() 调用规则**：
> - **必须调用**：`create_limit_order`, `create_market_order`, `close_position`, `create_stop_market_order`, `create_take_profit_market_order`
> - **不需要调用**：`cancel_all_orders` (仅取消挂单不改变持仓，且 _cancelled 标记应该保留)

> [!NOTE]
> **职责分离**：状态对象只管缓存和标记，**不包含回调函数**。
> 这样更易测试、更灵活，回调由外部辅助函数调用。

---

## 3. 辅助函数设计

辅助函数负责封装缓存/去重逻辑，并调用具体的回调函数。

### 3.1 `fetch_positions_cached`

```python
from typing import Tuple, Optional

def fetch_positions_cached(
    ctx: SymbolContext,
    callbacks: Callbacks
) -> Tuple[bool, Optional[CallbackResult[PositionsResponse]]]:
    """
    带缓存的 fetch_positions。

    返回: (executed, result)
        - executed=False, result=None: 复用缓存，未执行回调
        - executed=True, result=CallbackResult: 执行了回调
    """
    cached = ctx.get_positions_cache()
    if cached is not None:
        return (False, None)  # 复用缓存

    result = callbacks.fetch_positions([ctx.symbol])
    if result.success:
        ctx.set_positions_cache(result.data)
    return (True, result)
```

### 3.2 `cancel_all_orders_dedup`

```python
def cancel_all_orders_dedup(
    ctx: SymbolContext,
    callbacks: Callbacks
) -> Tuple[bool, Optional[CallbackResult[None]]]:
    """
    去重的 cancel_all_orders。

    返回: (executed, result)
        - executed=False, result=None: 跳过，未执行回调
        - executed=True, result=CallbackResult: 执行了回调
    """
    if ctx.is_cancelled():
        return (False, None)  # 跳过

    result = callbacks.cancel_all_orders(ctx.symbol)
    if result.success:
        ctx.mark_cancelled()
    return (True, result)
```

> [!TIP]
> **调用方职责**：根据 `executed` 判断是否需要检查 `result.success`。辅助函数不处理错误，不破坏工作流控制。

---

## 4. 状态流转示例

以下是一个典型周期内的状态变化流程：

| 步骤 | 操作 | `_positions_cache` | `_cancelled` | 说明 |
|------|------|--------------------|--------------|------|
| 1. 初始 | `SymbolContext(symbol)` | `None` | `False` | 新周期开始 |
| 2. 孤儿检查 | `fetch_positions_cached` | **缓存数据** | `False` | 实际调用 API |
| 3. 孤儿检查 | `cancel_all_orders_dedup` | 缓存数据 | **`True`** | 实际调用 API，标记已取消 |
| 4. 执行平仓 | `close_position` | ... | ... | 执行订单操作 |
| 5. 状态失效 | `invalidate()` | **`None`** | **`False`** | 重置状态 |
| 6. 信号动作 | `cancel_all_orders_dedup` | `None` | **`True`** | 再次调用 API（因为之前已重置） |
| 7. 开仓前检查 | `fetch_positions_cached` | **缓存数据** | `True` | 再次调用 API（因为之前已重置） |
| 8. 另一处检查 | `fetch_positions_cached` | **缓存数据** | `True` | **复用缓存**（不再调用 API） |
