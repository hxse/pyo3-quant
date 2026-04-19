# 最小指标目录示例

本文件只展示目标形态，非最终可运行代码。

示例按单个指标目录展开。新增指标时，应优先把该指标的扩展文件高内聚放到同一个目录中，方便后续扩展、审查和维护。

示例会省略部分具体类型签名；正式落地时，case、adapter、oracle、dataset、skip、tolerance 以及 adapter 回调的输入和返回，都必须使用 Pydantic 严格模型，并配合静态类型标注，通过 `just check` 与 `just test`。

## 1. 目录

以 `kc` 为例：

```text
py_entry/Test/indicators/kc/
  __init__.py
  cases.py
  adapter.py
  test_contracts.py
  fixtures/
    local_csv/
      custom_0.csv
```

共享后台位于：

```text
py_entry/Test/indicators/comparison/
```

指标目录只放该指标自己的扩展内容。

共享后台只放 runner、compare、datasets、reporting、oracle types 等通用能力。

## 2. `cases.py`

`cases.py` 只声明指标 comparison cases。

它不写 pta 调用细节，不写 engine 输出提取细节，不写比较逻辑，不写 warmup 数值真值。

默认声明 3 个标准 case。

每个标准 case 使用不同参数和不同 `DatasetId`。

推荐把公共参数提到顶部，再用 case 定义表和 list comprehension 生成 `STANDARD_CASES`。

```python
from pathlib import Path

from py_entry.Test.indicators.comparison.case import (
    DatasetId,
    IndicatorComparisonCase,
    LocalCsvOracle,
    PandasTaExact,
    WarmupCheck,
)

KC_EXACT = PandasTaExact(package="pandas_ta", talib=False, function="kc")
DEFAULT_TOLERANCE = {"default": {"rtol": 1e-5, "atol": 1e-8}}
KC_OUTPUTS = ["lower", "middle", "upper"]
WARMUP_ENABLED = WarmupCheck.enabled()

STANDARD_CASE_DEFS = [
    dict(
        id="kc-length-20-scalar-2-default-seed-42",
        indicator_key="kc_0",
        params={"length": 20, "scalar": 2.0},
        dataset_source=DatasetId("synthetic_default_seed_42"),
    ),
    dict(
        id="kc-length-35-scalar-1_5-trend-high-vol-seed-7",
        indicator_key="kc_1",
        params={"length": 35, "scalar": 1.5},
        dataset_source=DatasetId("synthetic_trend_high_vol_seed_7"),
    ),
    dict(
        id="kc-length-50-scalar-2_5-short-extreme-seed-11",
        indicator_key="kc_2",
        params={"length": 50, "scalar": 2.5},
        dataset_source=DatasetId("synthetic_short_extreme_seed_11"),
    ),
]

STANDARD_CASES = [
    IndicatorComparisonCase(
        indicator_base_name="kc",
        source_key="ohlcv_15m",
        outputs=KC_OUTPUTS,
        primary_validation_source=KC_EXACT,
        warmup_check=WARMUP_ENABLED,
        tolerance_policy=DEFAULT_TOLERANCE,
        **case_def,
    )
    for case_def in STANDARD_CASE_DEFS
]

LOCAL_CSV_CASES = [
    IndicatorComparisonCase(
        id="kc-local-csv-similarity",
        indicator_base_name="kc",
        indicator_key="kc_local_csv_0",
        source_key="ohlcv_15m",
        params={"length": 20, "scalar": 2.0},
        dataset_source=Path("fixtures/local_csv/custom_0.csv"),
        outputs=KC_OUTPUTS,
        primary_validation_source=LocalCsvOracle(
            compare_mode="similarity",
            # 特殊处理：CSV 来源、参数、列语义和对齐方式由用户在注释中说明。
        ),
        warmup_check=WarmupCheck.skip(
            reason="逃生舱：本地 CSV 样本不足以稳定执行 warmup 运行时校验。使用前必须报告用户并审查。",
        ),
    )
]

CASES = STANDARD_CASES + LOCAL_CSV_CASES
```

`CASES` 必须是 pytest 可直接参数化的最终 case 列表。

默认 3 个标准 case 在 `cases.py` 中定义，每个标准 case 绑定一组参数和一个具体 `DatasetId`。

可以用 `for` / list comprehension 生成 `CASES`，但只能用于构造最终 case 列表，不能把多个 dataset 隐藏到 runner 或 `test_contracts.py` 内部循环执行。

本地 CSV 使用 `Path` 类型。

相对 `Path` 默认相对当前指标目录解析。

`LocalCsvOracle` 不重复声明 `path`，也不暴露 `similarity_api`。

## 3. `adapter.py`

`adapter.py` 写该指标的取数与格式转换回调。

允许写 pta 特殊调用方式与 Rust engine 输出列提取方式。

不允许手动计算 Rust 指标，不允许绕过正式回测链路，不允许做 same / different 断言。

正式落地时，所有回调的输入与返回必须使用 Pydantic 严格模型，并配合静态类型标注。

```python
import pandas_ta as ta

from py_entry.Test.indicators.comparison.case import IndicatorAdapter
from py_entry.types import Param


def build_engine_params(case):
    return {
        case.source_key: {
            case.indicator_key: {
                "length": Param(case.params["length"]),
                "scalar": Param(case.params["scalar"]),
            }
        }
    }


def extract_engine_outputs(indicators_df, case):
    return {
        "lower": indicators_df[f"{case.indicator_key}_lower"],
        "middle": indicators_df[f"{case.indicator_key}_middle"],
        "upper": indicators_df[f"{case.indicator_key}_upper"],
    }


def build_oracle_outputs(source_df, case, oracle):
    pta_result = ta.kc(
        high=source_df["high"],
        low=source_df["low"],
        close=source_df["close"],
        length=case.params["length"],
        scalar=case.params["scalar"],
        talib=oracle.talib,
    )
    # 中文注释：pta 默认列解析属于 kc adapter 文件内部逻辑，不提升为公共 helper。
    lower_col, middle_col, upper_col = list(pta_result.columns)[:3]
    return {
        "lower": pta_result[lower_col],
        "middle": pta_result[middle_col],
        "upper": pta_result[upper_col],
    }


ADAPTER = IndicatorAdapter(
    build_engine_params=build_engine_params,
    extract_engine_outputs=extract_engine_outputs,
    build_oracle_outputs=build_oracle_outputs,
)
```

engine 侧保留两个回调：

1. `build_engine_params(case)`：在正式回测执行前构造 engine 参数。
2. `extract_engine_outputs(indicators_df, case)`：在正式回测执行后提取 engine 输出。

这两个阶段中间必须由共享后台执行正式回测链路，因此不合并成一个会运行 engine 的回调。

oracle 侧可以合并为一个 `build_oracle_outputs(...)` 回调，因为 pta 调用与 pta 输出解析属于同一侧的取数与格式转换。

adapter 的职责边界：

1. 可以做参数转换。
2. 可以做 pta 调用。
3. 可以做 engine / oracle 输出列提取。
4. 可以把输出转成统一比较格式。
5. 不能做比较、skip、fallback、异常吞噬或 Rust 指标计算。

## 4. `test_contracts.py`

`test_contracts.py` 是很薄的 pytest 入口。

薄入口的含义是：它只负责把该指标的 `CASES` 和 `ADAPTER` 接到共享 runner 上，并让 pytest 能按指标目录、函数名和 case id 定位失败。

允许写：

1. import `pytest`。
2. import 共享 runner 与共享 `case_id`。
3. import 本指标目录的 `CASES` 与 `ADAPTER`。
4. 两个固定 pytest 函数。
5. `pytest.mark.parametrize("case", CASES, ids=case_id)`。
6. 每个测试函数内部只调用一次对应的共享 runner。

不允许写：

1. 不允许在入口里拼接、筛选、排序或生成 case。
2. 不允许 `for` 循环批量执行 case。
3. 不允许 `if` 判断测试模式、oracle、dataset、参数或 skip。
4. 不允许 `try/except`、fallback、降级或异常吞噬。
5. 不允许读取 CSV、生成数据、构造 engine 参数或调用 pandas-ta。
6. 不允许写比较、容差、缺失值、warmup 或失败报告逻辑。
7. 不允许定义 helper 函数、局部 adapter、局部 case 或局部 fixture。

每个指标目录的 `test_contracts.py` 必须固定提供两个 pytest 函数：

1. `test_accuracy`
2. `test_warmup_contract`

这两个函数名必须固定，不能写成 `test_kc_accuracy`、`test_kc_warmup_contract` 等指标私有名字。

`test_contracts.py` 不得定义第三个 pytest `test_*` 函数；新增测试契约必须先扩展共享 runner 与本任务 Spec。

共享 pytest / conftest 层必须提供硬结构校验：只要某个指标目录包含 `cases.py` 与 `adapter.py`，就必须存在 `test_contracts.py`，且该文件通过 AST 或等价方式检查出 `test_accuracy` 与 `test_warmup_contract` 两个函数。缺任一函数、函数名不一致、多出未声明 pytest 函数或继续新增旧入口文件，都应在 collection 或 import 阶段明确失败。

```python
import pytest

from py_entry.Test.indicators.comparison.runner import (
    case_id,
    run_indicator_accuracy_case,
    run_indicator_warmup_case,
)

from .adapter import ADAPTER
from .cases import CASES


@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_accuracy(case):
    run_indicator_accuracy_case(case, ADAPTER)


@pytest.mark.parametrize("case", CASES, ids=case_id)
def test_warmup_contract(case):
    run_indicator_warmup_case(case, ADAPTER)
```

失败输出由共享后台统一负责，至少包含指标、参数、数据源、主校验源、输出列、失败行和短上下文。

warmup 不再有单独的 `warmup_cases.py`。

warmup runner 直接消费 `cases.py` 中的 `CASES`，复用同一份参数、source 与 dataset。

`IndicatorComparisonCase.warmup_check` 只表达是否参与 warmup contract 校验，以及极特殊 skip 逃生舱。

`warmup_check` 不承载 `warmup_bars`、`warmup_mode` 或任何 warmup 真值。

`resolve_indicator_contracts(...)` 是全局 warmup 真值入口。

要求：

1. `cases.py` 不写自定义 warmup 真值。
2. warmup runner 必须调用 `resolve_indicator_contracts(...)`。
3. 运行时输出校验必须消费聚合函数返回的 `contract.warmup_bars / contract.warmup_mode`。
4. warmup skip 只能通过 `WarmupCheck.skip(...)` 显式表达。
5. AI 使用 warmup skip 前必须报告用户并讨论。

## 5. 其他指标

单输出指标、多输出指标、expected same、expected different、local CSV 都使用同一目录形态。

差异只体现在：

1. `cases.py` 中声明的 case。
2. `adapter.py` 中该指标的 pta 调用与输出提取。
3. `cases.py` 中该指标的 `warmup_check`。
4. `test_contracts.py` 中固定的两个 pytest 入口函数。

共享后台不承载指标特有逻辑。
