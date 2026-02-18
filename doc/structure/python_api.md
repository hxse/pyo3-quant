# Python 接口文档（当前版）

本文档描述当前 Python 侧的核心入口与常用类型。

## 1. 核心入口：`Backtest`

当前统一入口是 `py_entry.runner.Backtest`，不再使用旧版 `BacktestRunner` 路径。

```python
from py_entry.runner import Backtest

bt = Backtest(
    data_source=...,
    indicators=...,
    signal=...,
    backtest=...,
    performance=...,
    signal_template=...,
    engine_settings=...,
    enable_timing=True,
)

result = bt.run()
```

## 2. `Backtest` 核心方法

- `run(params_override: Optional[SingleParamSet] = None) -> RunResult`
- `batch(param_list: list[SingleParamSet]) -> BatchResult`
- `optimize(config: Optional[OptimizerConfig] = None, params_override: Optional[SingleParamSet] = None) -> OptimizeResult`
- `optimize_with_optuna(config: Optional[OptunaConfig] = None, params_override: Optional[SingleParamSet] = None) -> OptunaOptResult`
- `walk_forward(config: Optional[WalkForwardConfig] = None, params_override: Optional[SingleParamSet] = None) -> WalkForwardResultWrapper`
- `sensitivity(config: Optional[SensitivityConfig] = None, params_override: Optional[SingleParamSet] = None) -> SensitivityResult`

## 3. `RunResult` 常用方法

- `format_for_export(config: FormatResultsConfig) -> Self`
- `save(config: SaveConfig) -> Self`
- `upload(config: UploadConfig) -> Self`
- `display(config: DisplayConfig | None = None)`

说明：`display()` 返回 HTML 或 widget，取决于运行环境（Jupyter / marimo / 其他）。

## 4. 数据源类型（`data_source`）

来自 `py_entry.data_generator`：

- `DataGenerationParams`（模拟数据）
- `OhlcvDataFetchConfig`（HTTP 获取数据）
- `DirectDataConfig`（直接传入 DataFrame）

说明：`DataSourceConfig` 是以上三者的联合类型，不是单一“模拟数据”入口。

### 4.1 `DataGenerationParams`（模拟生成）

```python
from py_entry.data_generator import DataGenerationParams

data_source = DataGenerationParams(
    timeframes=["15m", "1h"],
    start_time=None,
    num_bars=2000,
    fixed_seed=42,
    base_data_key="ohlcv_15m",
)
```

### 4.2 `OhlcvDataFetchConfig`（从服务端获取）

```python
from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.io import load_local_config

request_config = load_local_config()
data_source = OhlcvDataFetchConfig(
    config=request_config,
    exchange_name="binance",
    market="future",
    symbol="BTC/USDT",
    timeframes=["15m", "1h"],
    since=None,
    limit=3000,
    enable_cache=True,
    mode="sandbox",
    base_data_key="ohlcv_15m",
)
```

### 4.3 `DirectDataConfig`（直接喂自有数据）

```python
import polars as pl
from py_entry.data_generator import DirectDataConfig

df_15m = pl.DataFrame(...)  # 你自己的 OHLCV 数据
df_1h = pl.DataFrame(...)

data_source = DirectDataConfig(
    data={
        "ohlcv_15m": df_15m,
        "ohlcv_1h": df_1h,
    },
    base_data_key="ohlcv_15m",
)
```

## 5. 常用参数类型

来自 `py_entry.types`：

- `Param`
- `BacktestParams`
- `PerformanceParams`, `PerformanceMetric`
- `SignalGroup`, `SignalTemplate`, `LogicOp`
- `SettingContainer`, `ExecutionStage`
- `OptimizerConfig`, `OptunaConfig`, `WalkForwardConfig`, `SensitivityConfig`

枚举调用建议：优先使用 `str(enum)` 或 `enum.as_str()`，不要依赖 `.value`。

## 6. 最小完整示例

```python
from py_entry.runner import Backtest
from py_entry.data_generator import DataGenerationParams

cfg = DataGenerationParams(
    timeframes=["15m"],
    start_time=None,
    num_bars=2000,
    fixed_seed=42,
    base_data_key="ohlcv_15m",
)

bt = Backtest(data_source=cfg)
result = bt.run()

if result.summary is not None:
    print(result.summary.performance)
```

## 7. 与策略/Notebook 分层的关系

- `.py`：AI 调试入口（`__main__` 输出摘要）
- `ipynb`：人类调试入口（图表与探索）
- notebook 仅导入并调用 `.py` 封装函数，不承载核心策略实现

参见：`doc/structure/strategy_cross_module_plan.md`
