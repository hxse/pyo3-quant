# 当前项目测试模式

## 1. 现有主链路

当前指标测试主链路集中在：

```text
py_entry/Test/indicators/conftest.py
py_entry/Test/indicators/indicator_test_template.py
py_entry/Test/utils/comparison_tool.py
py_entry/Test/indicators/test_indicator_warmup_contract.py
py_entry/Test/indicators/test_<indicator>.py
```

核心执行方式：

1. 测试构造 `DataGenerationParams` 与 `indicators_params`。
2. `run_indicator_backtest(...)` 通过 `make_backtest_runner(...)` 执行正式回测链路。
3. engine 停在 `ExecutionStage.Indicator`。
4. engine 输出来自 `backtest_results[0].indicators[source_key]`。
5. oracle 输出由 `pandas_ta` 标准函数调用生成。
6. 对比工具检查长度、前导 NaN 数量和数值近似。

## 2. 已有优点

1. 没有绕过 Rust 内置指标系统计算 engine 输出。
2. 使用正式 `Param` / `IndicatorsParams` 口径表达参数。
3. 单输出和多输出指标都已有 extractor 模式。
4. warmup contract 已有静态契约与运行时输出双重校验。
5. 已存在“预期不同”的测试诉求，例如对齐 `talib=true` 但不对齐 `talib=false` 的指标。

## 3. 当前不足

1. oracle 选择不是显式对象。
2. `assert_mode_*` 语义过粗，无法区分主校验源与 secondary oracle assertion。
3. 缺失值 mask 比较不够严格，容易只对前导 NaN 敏感。
4. 参数和数据覆盖太薄。
5. 多输出列映射散落在各测试文件中。
6. 本地 CSV 交叉验证没有正式契约。
7. 显式 skip、特殊容差注释和已知偏差说明没有统一口径。

## 4. 重构原则

重构允许拆文件、改 helper、重写模板。

但以下方向必须保持：

1. engine 输出仍来自正式回测链路。
2. oracle 只作为测试真值源，不进入生产链路。
3. 对比强度只能增强或显式新增，不得静默放宽。
4. 预期不一致必须从模糊布尔参数升级为具名 secondary oracle assertion。
5. 现有重点校验 helper 优先冻结并复用；若 exact 校验需要增强，应在现有语义基础上做最小扩展，避免重写时引入漂移。
