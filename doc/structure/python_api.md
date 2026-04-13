# Python 接口文档（当前版）

本文档描述当前 Python 侧的核心入口与常用类型。
以下内容已对齐 `2026-04-05 wf export display and precheck cleanup` 与 `2026-03-10 unified ranges warmup wf` 的当前正式口径。

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

- `run(params_override: Optional[SingleParamSet] = None) -> SingleBacktestView`
- `batch(param_list: list[SingleParamSet]) -> BatchBacktestView`
- `optimize(config: Optional[OptimizerConfig] = None, params_override: Optional[SingleParamSet] = None) -> OptimizationView`
- `optimize_with_optuna(config: Optional[OptunaConfig] = None, params_override: Optional[SingleParamSet] = None) -> OptunaOptimizationView`
- `walk_forward(config: WalkForwardConfig, params_override: Optional[SingleParamSet] = None) -> WalkForwardView`
- `sensitivity(config: Optional[SensitivityConfig] = None, params_override: Optional[SingleParamSet] = None) -> SensitivityView`
- `resolve_indicator_contracts(params_override: Optional[SingleParamSet] = None) -> IndicatorContractReport`

## 3. 导出与显示正式入口

- `SingleBacktestView.prepare_export(config: FormatResultsConfig) -> PreparedExportBundle`
- `WalkForwardView.prepare_export(config: FormatResultsConfig) -> PreparedExportBundle`
- `PreparedExportBundle.save(config: SaveConfig) -> Self`
- `PreparedExportBundle.upload(config: UploadConfig) -> Self`
- `PreparedExportBundle.display(config: DisplayConfig | None = None)`

说明：显示层正式消费 `PreparedExportBundle`，不再直接消费结果 view。

## 3.1 `SettingContainer` 正式字段

- `stop_stage: ExecutionStage`
- `artifact_retention: ArtifactRetention`

模式约束：

- `Backtest.run()` / `Backtest.batch()` 消费实例持有的 `engine_settings`
- `Backtest.walk_forward()` 固定使用 `Performance + AllCompletedStages`
- `Backtest.optimize()` / `Backtest.sensitivity()` / `Backtest.optimize_with_optuna()` 固定使用 `Performance + StopStageOnly`

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
    end_backfill_min_step_bars=5,
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
- `SettingContainer`, `ExecutionStage`, `ArtifactRetention`
- `OptimizerConfig`, `OptunaConfig`, `WalkForwardConfig`, `SensitivityConfig`
- `WfWarmupMode`

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

print(result.raw.performance)
```

## 6.1 WF 推荐调用顺序

```python
wf_cfg = ...
wf = bt.walk_forward(wf_cfg)
print(wf.aggregate_test_metrics)
```

## 7. 与策略/Notebook 分层的关系

- `.py`：AI 调试入口（`__main__` 输出摘要）
- `ipynb`：人类调试入口（图表与探索）
- notebook 仅导入并调用 `.py` 封装函数，不承载核心策略实现

参见：`doc/structure/strategy_cross_module_plan.md`
