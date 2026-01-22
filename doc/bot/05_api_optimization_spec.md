# API 调用优化（Scoped Proxy 模式）

本文档描述交易机器人 API 调用的优化设计，旨在减少每个执行周期内对交易所 API 的冗余请求。

> [!NOTE]
> 这是一个**可选**的高级功能，但强烈建议实现以提高运行效率并节省 API 权重。

---

## 1. 设计理念：代理模式 (Proxy Pattern)

### 1.1 核心思想

为了保证**业务逻辑的代码纯净性**（不混杂缓存逻辑）和**零侵入性**（不需要修改现有函数签名），采用 **Scoped Callbacks Proxy（作用域回调代理）** 模式。

- **零侵入**：`RuntimeChecks` 和 `Executor` 不需要知道缓存的存在，它们调用的仍然是标准的 `Callbacks` 接口。
- **作用域隔离**：每次主循环处理一个 Symbol 时，创建一个临时的代理对象 `OptimizationCallbacks`，生命周期仅限于该 Symbol 的处理过程。
- **自动管理**：缓存的命中、失效和去重逻辑全部封装在代理类内部。

> [!IMPORTANT]
> **严格的作用域限制 (Strict Scope)**
> 本缓存机制**严格限制**在：
> - **同一周期 (Same Cycle)**
> - **同一品种 (Same Symbol)**
> - **同一策略 (Same Strategy)**
> 的执行上下文内部。
>
> **跨周期、跨品种、跨策略**的请求**绝不**共享缓存。每次循环开始时都会创建一个全新的空白代理对象，确保状态完全隔离。

### 1.2 解决的问题

在一个周期循环内，同一个 Symbol 可能因不同逻辑多次调用同一个 API：

1.  **`fetch_positions`**：
    - 孤儿订单检查（Orphan Check）会调用。
    - 重复开仓检查（Duplicate Check）会调用。
    - **优化**：第一次调用后缓存结果，后续调用直接返回缓存。

2.  **`cancel_all_orders`**：
    - 信号解析器可能生成取消动作。
    - 孤儿订单检查也可能触发取消。
    - **优化**：如果已经执行过一次成功取消，后续重复调用直接返回成功（不再发网络请求）。

3.  **缓存失效（Invalidation）**：
    - 当执行了**写操作**（下单、平仓）后，持仓状态已改变，之前的缓存必须失效。

---

## 2. 详细设计：OptimizationCallbacks

`OptimizationCallbacks` 是 `Callbacks` 协议的一个包装器（Wrapper）。

### 2.1 类结构

```python
class OptimizationCallbacks:
    """
    作用域内的 API 优化代理。
    生命周期：仅限于单次 Loop 的单个 Symbol 处理过程。
    """

    def __init__(self, inner: Callbacks, symbol: str):
        self._inner = inner
        self._symbol = symbol

        # 状态存储
        self._positions_cache: Optional[PositionsResponse] = None
        self._cancelled_all: bool = False

    def __getattr__(self, name):
        # 对于未显式定义的方法，直接透传给内部 callbacks
        return getattr(self._inner, name)
```

### 2.2 读请求优化 (Caching)

**`fetch_positions`**:

1.  **检查缓存**：如果请求的 `symbols` 列表仅包含当前 `_symbol` 且 `_positions_cache` 存在，直接返回缓存数据。
2.  **透传请求**：否则调用 `_inner.fetch_positions`。
3.  **更新缓存**：如果请求成功且针对的是当前 `_symbol`，将结果存入 `_positions_cache`。

### 2.3 写请求失效 (Invalidation)

**以下写操作必须触发缓存失效**（即置 `_positions_cache = None`）：

- `create_limit_order`
- `create_market_order`
- `create_stop_market_order`
- `create_take_profit_market_order`
- `close_position`

> [!IMPORTANT]
> **失效原则**：任何可能改变持仓状态的操作都必须清除持仓缓存，确保下一次读取获取到最新状态（或者迫使程序重新拉取）。

### 2.4 重复请求去重 (Deduplication)

**`cancel_all_orders`**:

1.  **检查标记**：如果 `_cancelled_all` 为 `True`，直接返回成功（模拟响应），不再调用底层 API。
2.  **透传请求**：否则调用 `_inner.cancel_all_orders`。
3.  **设置标记**：如果请求成功，设置 `_cancelled_all = True`。

> [!IMPORTANT]
> **严谨性修正**：`_cancelled_all` 标记在任何**创建订单**的操作发生后**必须重置为 False**。
>
> 具体包括以下方法：
> - `create_limit_order`
> - `create_stop_market_order`
> - `create_take_profit_market_order`
>
> **原因**：一旦创建了新订单，“当前没有挂单”这一状态即被打破。如果后续逻辑再次请求 `cancel_all_orders`（例如复杂的反手流程，或者下单后发现某些极端条件需要立即撤单），必须真实发送撤单请求。
> **原则**：优化层不能假设上层逻辑的调用顺序，必须保证状态的绝对正确性。新订单生成 = `_cancelled_all` 失效。

---

## 3. 集成方式

在 `TradingBot` 的主循环 `_process_symbol` 中：

```python
async def _process_symbol(self, params: StrategyParams) -> StepResult:
    # 1. 创建代理 (Scope 开始)
    scoped_callbacks = OptimizationCallbacks(self.callbacks, params.symbol)

    # 2. 注入代理
    # RuntimeChecks 和 Executor 接收的是 scoped_callbacks
    # 它们内部调用的 fetch_positions 等方法会被自动拦截
    scoped_runtime_checks = RuntimeChecks(scoped_callbacks)
    scoped_executor = ActionExecutor(scoped_callbacks, scoped_runtime_checks)

    # 3. 执行逻辑 (完全无感)
    # ...
    # 传递 scoped_runtime_checks 和 scoped_executor 给执行函数
    return self._execute_signal(..., scoped_runtime_checks, scoped_executor)
```

---

## 4. 优势总结

| 维度 | 说明 |
|------|------|
| **代码整洁** | 业务逻辑层（Checks/Executor）不需要任何修改，不需要到处传 `ctx`。 |
| **安全性** | 缓存失效逻辑封装在代理内部，只要调了下单就会失效，不会遗漏。 |
| **可测试性** | 可以单独为 `OptimizationCallbacks` 编写单元测试，验证缓存命中和失效逻辑。 |
| **灵活性** | 如果未来想全局禁用优化，只需在创建时直接传 `self.callbacks` 即可，零成本切换。 |
