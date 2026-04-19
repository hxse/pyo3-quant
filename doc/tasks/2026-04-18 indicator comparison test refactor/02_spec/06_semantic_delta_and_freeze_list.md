# 语义新增与冻结清单

本清单是后续重构审查的最低基线，不是审查边界。执行与 review 仍需完整阅读 diff，防止清单外漂移。

## 1. 新增语义逻辑

### ADD-001：主校验源单选

每个指标 case 必须且只能有一个主校验源。

新增原因：防止同一个 case 同时尝试多个真值源，导致“哪个过就算哪个”的漂移。

### ADD-002：用户声明主校验源

四级 strict exact oracle 的项目优先级固定为：

1. `pandas-ta (talib=true)`
2. `pandas-ta (talib=false)`
3. `pandas-ta-classic (talib=true)`
4. `pandas-ta-classic (talib=false)`

该优先级用于用户和 Spec 判断。程序只执行 case 中声明的主校验源，不判断优先级、不自动降级、不回退。

### ADD-003：strict exact 禁止 similarity

前四级 oracle 只能做严格逐点对比。

similarity、correlation、方向一致率不能作为通过条件。

### ADD-004：local CSV 后备校验源

用户确认四级 strict exact oracle 全部不可用时，允许使用 `local_csv`。

`local_csv` 可以选择 exact 或 similarity。来源、参数、列语义和对齐规则由用户在 case 附近用注释说明。

`local_csv` 支持自动生成数据与本地 CSV 数据两种模式；本地 CSV 数据由 `Path` 类型的 `dataset_source` 指向 `.csv` 文件，`LocalCsvOracle` 不重复声明 `path`。

### ADD-005：secondary oracle assertion

新增 secondary oracle assertion，用于表达“主校验源之外，另一个 oracle 应当 same 或 different”。

该语义替代当前粗粒度的 `assert_mode_* = False`。

`expected_different` 必须精确识别 same comparator 的 comparison mismatch，不允许宽泛捕获 `AssertionError`、`Exception` 或依赖异常消息字符串。

### ADD-006：case manifest 与指标目录入口契约

新增 case manifest / case contract，用于集中声明参数、数据集、逻辑输出列、主校验源、容差、缺失值特殊处理、secondary oracle assertion 与 warmup_check；每个指标目录 pytest 入口固定为 `test_contracts.py`，并由共享 pytest 结构校验强制只包含 `test_accuracy` 与 `test_warmup_contract`。

### ADD-007：全列缺失值 mask strict 校验

strict exact comparison 必须检查全列缺失值 mask。

这比当前只重点检查前导 NaN 数量更严格。

### ADD-008：标准 case 覆盖扩展

每个指标默认新增 3 个标准 case，复用现有 `DataGenerationParams` 与 `generate_multi_timeframe_ohlcv(...)`，通过不同参数、seed、趋势、波动、极端行情和短样本覆盖更多真实 K 线场景。

`generate_ohlcv(...)` 只作为多周期生成器内部子调用，不作为本任务标准测试入口。

### ADD-009：similarity 只使用现成 API

`local_csv` 的 similarity 模式默认只使用 `pandas_ta.utils.df_error_analysis(...)`。

不得手写相似性算法。

额外误差指标属于特殊处理，必须注释、报告并审查。

### ADD-010：默认行为与特殊处理边界

新增 `09_default_and_special_handling.md`，明确什么是默认行为、什么是特殊处理。

特殊处理必须注释说明；AI 使用前必须报告用户并讨论，不得静默启用。

### ADD-011：失败上下文契约

新增 `10_failure_reporting_contract.md`，要求失败信息定位到校验模式、指标、列、行、参数、数据源与 oracle。
失败输出应打印短上下文，默认最多 7 行，避免大量指标对齐失败时日志失控。

## 2. 冻结语义逻辑

### FRZ-001：engine 输出必须来自正式回测链路

来源：

```text
py_entry/Test/indicators/conftest.py::run_indicator_backtest
```

冻结语义：

指标测试必须通过 `make_backtest_runner(...)` 执行正式链路。engine 指标结果必须来自 Rust 回测引擎本身输出，不允许 Python 测试层手动计算 engine 指标结果。

### FRZ-002：指标阶段执行语义保持

来源：

```text
ExecutionStage.Indicator
ArtifactRetention.StopStageOnly
```

冻结语义：

指标准确性测试仍应停在指标阶段，只保留该阶段所需产物。

### FRZ-003：run_indicator_backtest 输入输出语义保持

来源：

```text
run_indicator_backtest(data_params, indicators_params) -> (backtest_results, data_pack)
```

冻结语义：

输入仍是数据生成参数与指标参数，输出仍能取得 raw `ResultPack` 与 `DataPack`。

允许重构返回类型包装，但不得改变调用方可获得 engine indicators 与 source 数据的能力。

### FRZ-004：engine indicators 读取路径保持

来源：

```text
backtest_results[0].indicators[source_key]
```

冻结语义：

测试对比使用的 engine 输出仍来自 `ResultPack.indicators`。

不得改成绕开 `ResultPack` 的私有中间结构。

### FRZ-005：source OHLCV 读取路径保持

来源：

```text
data_pack.source[source_key]
```

冻结语义：

oracle 计算输入数据仍复用同一次正式执行产生的同一个 `DataPack` source。

### FRZ-006：参数入口语义保持

来源：

```text
py_entry.types.Param
IndicatorsParams
```

冻结语义：

engine 参数仍通过仓库正式参数体系传入。

case manifest 使用普通值表达参数；执行前必须转换为正式参数对象。

### FRZ-007：pandas-ta 调用方式保持

来源：

```text
import pandas_ta as ta
ta.xxx(...)
```

冻结语义：

正式 oracle 调用继续使用标准函数调用，不使用 `ohlc.ta.xxx(...)` 作为正式基准。

### FRZ-008：输出列命名语义保持

来源：

```text
单输出：<indicator_key>
多输出：<indicator_key>_<suffix>
```

冻结语义：

测试重构不得改变 engine 输出列契约。

### FRZ-009：当前正向一致校验不得放宽

来源：

```text
py_entry/Test/utils/comparison_tool.py::assert_indicator_same
```

冻结语义：

已有“应当一致”的测试，迁移后必须是当前校验逻辑的超集，不得比当前更宽松，不得丢失任何现有校验逻辑。

允许新增更严格规则，例如全列缺失值 mask 检查。

### FRZ-010：当前预期不一致语义必须迁移

来源：

```text
assert_mode_pandas_ta=False
assert_mode_talib=False
```

冻结语义：

已有“预期不同”的有效测试诉求不得删除。

迁移后必须以 secondary oracle assertion 的 `expected_different` 表达。

### FRZ-011：warmup 静态契约校验保持

来源：

```text
resolve_indicator_contracts(...)
contracts_by_indicator
```

冻结语义：

warmup contract 测试仍必须校验静态契约中的 `warmup_bars` 与 `warmup_mode`。

### FRZ-012：warmup 运行时输出校验保持

来源：

```text
test_indicator_warmup_contract.py::_assert_warmup_contract
```

冻结语义：

运行时输出必须与 warmup contract 一致。

`Strict` 模式下非预热段不得存在缺失值。

`Relaxed` 模式下非预热段不得整行全空。

### FRZ-013：warmup scaling scan 保持

来源：

```text
test_indicator_warmup_contract.py::test_indicator_warmup_scaling_scan
```

冻结语义：

参数放大时 warmup 单调不减的校验诉求必须保留。

### FRZ-014：布尔 false 不得被当作缺失值

来源：

```text
test_divergence_window_false_not_killed_by_strict
```

冻结语义：

布尔输出中的 `False` 是有效值，不得被 Strict 缺失检查误杀。

### FRZ-015：不修改生产指标语义

来源：本任务范围。

冻结语义：

本任务只重构测试系统，不改变任何生产指标公式、参数、输出列或 warmup contract。

### FRZ-016：现有比较 helper 语义作为下限

来源：

```text
py_entry/Test/utils/comparison_tool.py
py_entry/Test/indicators/indicator_test_template.py
```

冻结语义：

当前 positive comparison 的长度校验、前导 NaN 校验、布尔列逐点相等、数值列 `allclose` 等语义是重构后的下限。

exact comparison 可以在此基础上新增全列缺失值 mask 校验和更清晰的 pytest case 维度，但不得丢失当前 helper 已提供的任何校验。

### FRZ-017：warmup 默认不可跳过

来源：`test_indicator_warmup_contract.py`
冻结语义：comparison case 迁移不得隐式取消 warmup 静态契约、运行时输出契约或 scaling scan；不得内联 `expected_bars`、`warmup_mode` 或类似 warmup 真值字段。
warmup 全局真值入口必须是 `resolve_indicator_contracts(...)`；warmup runner 复用 `cases.py` 的 `CASES` 与 `warmup_check`，不得另起一套 warmup 真值。
运行时输出校验必须消费聚合函数返回的 `contract.warmup_bars` 与 `contract.warmup_mode`；跳过 warmup 是逃生舱，只能作为显式特殊处理，并且必须注释说明、报告用户并讨论。
