# Pytest 测试统一方案说明

## 1. 目标

本次统一的目标是减少 `py_entry/Test` 下重复的“数据配置 + 回测配置 + 引擎配置 + runner 组装”代码，降低以下问题：

- 同一默认值在多个测试文件中漂移（尤其是回测执行开关默认值）
- 新增参数后多处漏改
- 同类测试模块写法不一致，阅读成本高

统一原则：

- 保持测试语义与断言逻辑不变，只收敛“构造与组装”层
- 允许特例参数透传，不强行抹平场景差异
- 优先在 fixture 与 helper 层收敛，避免改动每条测试断言

## 2. 共享入口

共享模块路径：`py_entry/Test/shared/`

当前核心入口：

- `py_entry/Test/shared/backtest_builders.py`
- `py_entry/Test/shared/strategy_runner.py`

### 2.1 backtest_builders

- `make_data_generation_params(...)`
  - 统一 `DataGenerationParams` 的常用默认值
  - 支持 `**extra_fields` 透传（例如 `allow_gaps`）
- `make_backtest_params(...)`
  - 统一 `BacktestParams` 默认值
  - 默认执行相关布尔开关为 `False`
- `make_engine_settings(...)`
  - 统一 `SettingContainer` 创建
- `make_ma_cross_template(...)`
  - 统一常用均线交叉模板
- `make_backtest_runner(...)`
  - 统一 `Backtest(...)` 组装
- `make_optimizer_sma_atr_components(...)`
  - 统一 optimizer benchmark 场景常用组件（indicators/template/backtest）

### 2.2 strategy_runner

- `run_strategy_backtest(strategy)`
  - 统一策略注册表场景的回测执行入口
- `extract_backtest_df_with_close(results, data_dict)`
  - 统一从结果中提取 `backtest_result`，并在可用时补 `close` 列

## 3. 当前已迁移模块

- `py_entry/Test/backtest/common_tests/conftest.py`
- `py_entry/Test/backtest/precision_tests/conftest.py`
- `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`
- `py_entry/Test/backtest/strategies/*.py`（pyo3 配置侧）
- `py_entry/Test/backtest/correlation_analysis/*`
- `py_entry/Test/performance/conftest.py`
- `py_entry/Test/result_export/conftest.py`
- `py_entry/Test/sensitivity/test_sensitivity.py`
- `py_entry/Test/execution_control/test_execution_control.py`
- `py_entry/Test/optimizer_benchmark/*`（核心测试与基准脚本）
- `py_entry/Test/signal/test_signal_generation.py`
- `py_entry/Test/signal/test_leading_nan.py`
- `py_entry/Test/signal/test_zone_cross_boundary.py`
- `py_entry/Test/indicators/conftest.py`
- `py_entry/Test/indicators/extended/test_opening_bar.py`
- `py_entry/Test/data_generator/conftest.py`
- `py_entry/Test/data_generator/test_generate_data_dict_integration.py`

## 4. 暂未迁移（建议后续批次）

以下模块保持独立场景特征，建议后续按需迁移：

- `py_entry/Test/backtest/strategies/*.py`
  - 已迁移到 shared 构造器，策略语义保持显式定义
- `py_entry/Test/data_generator/*`
  - 仅部分迁移（参数构造层），其余用例保持数据生成器本体导向
- `py_entry/Test/backtest/correlation_analysis/*`
  - 已完成核心迁移，后续仅保留小范围优化

## 5. 使用建议

新测试优先使用 shared 入口，避免重复拼装：

```python
from py_entry.Test.shared import (
    make_data_generation_params,
    make_backtest_params,
    make_engine_settings,
    make_backtest_runner,
)
```

典型模式：

```python
data = make_data_generation_params(timeframes=["15m"], num_bars=500)
params = make_backtest_params(fee_pct=0.0005)
settings = make_engine_settings(return_only_final=True)

bt = make_backtest_runner(
    data_source=data,
    indicators={"ohlcv_15m": {"sma": {"period": Param(20)}}},
    backtest=params,
    engine_settings=settings,
)
```

## 6. 验证与执行注意事项

串行验证顺序：

1. `just check`
2. `just test`

实践注意：

- 不要并行运行多个 `just test-py ...`（尤其在本地同进程并发时）
- 并发触发 `maturin develop` 可能导致临时构建产物竞争，出现 `.so malformed` 类错误
- 出现该类错误时，直接串行重跑目标测试即可恢复

## 7. 后续演进建议

- 为 `py_entry/Test/shared` 增加更细粒度场景工厂（例如 signal 专用）
- 在 PR 审查中新增一条约束：新增测试不得手写重复的 `Backtest(...)` 组装样板
- 在文档与代码同步更新时，优先调整 shared 层默认值，避免多点手改
