# Pytest 测试约定（当前版）

## 1. 目标

在不过度工程化的前提下，保持测试策略来源清晰、执行路径稳定。

## 2. 测试中的两类策略来源

## 2.1 公共回归策略

来源：`py_entry/strategies` 注册表。

用途：

1. 通用回归。
2. 跨模块共享行为验证。
3. 稳定基线样板。

## 2.2 自定义测试场景策略

来源：测试文件内最小构造（`Backtest(...)` 或 `make_backtest_runner(...)`）。

用途：

1. 边界条件。
2. 回归 bug 最小复现。
3. 指标/信号局部精确断言。

说明：

1. 这类策略不追求复用，追求定位效率。
2. 策略实现层（`example` / `py_entry/strategies` / `py_entry/private_strategies`）优先直接使用配置类型（如 `DataGenerationParams` / `DirectDataConfig`）。
3. 测试统一常量放在 `py_entry/Test/shared/constants.py`（例如 `TEST_START_TIME_MS`）。

## 3. 数据源约定（`DataSourceConfig`）

测试里构造 `Backtest(data_source=...)` 时，`data_source` 可以是三种：

1. `DataGenerationParams`（模拟数据）
2. `OhlcvDataFetchConfig`（服务端拉取）
3. `DirectDataConfig`（直接喂 DataFrame）

建议：

1. 单元测试优先 `DataGenerationParams` 或 `DirectDataConfig`。
2. 涉及接口联调时再用 `OhlcvDataFetchConfig`。

## 4. private live 策略默认规则

对于 `py_entry/private_strategies/live` 中已注册策略：

1. 默认在 `Test` 跑一遍最小 smoke（防低级错误）。
2. 默认可被交易机器人执行。

说明：`live` 是实盘策略区，不要求稳定，可高频改动。

当前实现建议：

1. 使用 `py_entry.trading_bot.LiveStrategyCallbacks` 读取 live 注册并桥接给机器人。
2. 在 `py_entry/Test/trading_bot/test_live_strategy_callbacks.py` 维持最小 smoke。

## 5. 最小示例

## 5.1 公共回归策略

```python
from py_entry.strategies import get_strategy
from py_entry.runner import Backtest

cfg = get_strategy("sma_crossover")
result = Backtest(
    data_source=cfg.data_config,
    indicators=cfg.indicators_params,
    signal=cfg.signal_params,
    backtest=cfg.backtest_params,
    signal_template=cfg.signal_template,
    engine_settings=cfg.engine_settings,
    performance=cfg.performance_params,
).run()

assert result.summary is not None
```

## 5.2 自定义测试场景

```python
from py_entry.runner import Backtest
from py_entry.data_generator import DataGenerationParams

data_source = DataGenerationParams(
    timeframes=["15m"],
    start_time=None,
    num_bars=300,
    fixed_seed=42,
    base_data_key="ohlcv_15m",
)

result = Backtest(data_source=data_source).run()
assert result.summary is not None
```

## 6. 执行顺序

1. `just check`
2. `just test`

与项目 `AGENTS.md` 保持一致。

## 7. 导入副作用约束（重要）

为避免测试与 notebook 场景被意外拉起 `backtesting`（触发 Bokeh/Jupyter 副作用）：

1. 策略注册链路中的 `pyo3.py` 禁止顶层导入 `btp.py` 或 `backtesting`。
2. 若需要 `btp_strategy_class`，必须在 `get_config()` 内惰性导入（函数内 `from .btp import ...`）。
3. `py_entry/strategies/__init__.py` 不应在模块顶层导入 `backtesting` 或调用 `set_bokeh_output(...)`。

检查建议：

1. 新增/修改策略后，至少验证一次仅导入策略配置不会触发 Bokeh 警告。
2. 保持 `just check` 通过，避免因导入链路变化引入隐式回归。
