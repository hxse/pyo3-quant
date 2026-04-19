# 指标目录结构

## 1. 目标

指标测试扩展采用高内聚目录结构。

每个指标自己的 case、adapter、pytest contract 入口与 fixture 放在同一个指标目录中。

这样做的目的，是让后续新增、审查、迁移和维护某个指标时，只需要优先进入该指标目录，而不是在共享后台与多个平铺测试文件之间来回跳转。

共享后台只承载通用执行框架，不承载具体指标细节。

## 2. 目录结构

目标结构：

```text
py_entry/Test/indicators/
  comparison/
    case.py
    runner.py
    compare.py
    datasets.py
    reporting.py
    oracle_types.py
    test_global_warmup_contracts.py

  kc/
    __init__.py
    cases.py
    adapter.py
    test_contracts.py
    fixtures/
      local_csv/
```

`kc/` 只是示例。其他指标使用同样结构。

## 3. 指标目录职责

每个指标目录只描述该指标自己的测试扩展内容。

### `cases.py`

声明指标 comparison cases。

允许写：

1. 指标名。
2. indicator key。
3. source key。
4. 参数。
5. 输出列。
6. 主校验源。
7. secondary oracle assertion。
8. 容差特殊处理。
9. case skip 或 output skip 特殊处理。

不允许写：

1. 正式回测执行逻辑。
2. same / different 比较逻辑。
3. 自动降级或回退逻辑。
4. warmup 数值真值。

### `adapter.py`

声明该指标如何适配 engine 与 oracle。

允许写回调函数：

1. build engine params。
2. extract engine outputs。
3. build oracle outputs。
4. 将 engine 与 oracle 输出转换为统一比较格式。

不允许写：

1. 手动计算 Rust 指标。
2. 绕过正式回测链路。
3. same / different 断言。
4. 容差判断。
5. skip 判断。
6. oracle 自动降级或 fallback。
7. 异常吞噬。

Rust engine 结果只能来自后台 runner 执行正式回测链路后的 `ResultPack.indicators`。

engine 侧保留两个回调：一个在正式回测前构造参数，一个在正式回测后提取输出。二者中间必须由共享后台执行正式回测链路，因此不合并成一个会运行 engine 的回调。

oracle 侧可以合并为一个 `build_oracle_outputs(...)` 回调，因为 pta 调用与 pta 输出解析属于同一侧的取数与格式转换。

所有 adapter 回调的输入与返回必须使用 Pydantic 严格模型，并配合静态类型标注。

### `test_contracts.py`

只做 pytest 薄入口。

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

每个 `test_contracts.py` 必须固定提供两个 pytest 函数：

1. `test_accuracy`
2. `test_warmup_contract`

函数名必须固定，不能按指标名改写。

`test_contracts.py` 不得定义第三个 pytest `test_*` 函数；新增测试契约必须先扩展共享 runner 与本任务 Spec。

共享 pytest / conftest 层必须提供硬结构校验：

1. 包含 `cases.py` 与 `adapter.py` 的指标目录，必须包含 `test_contracts.py`。
2. `test_contracts.py` 必须通过 AST 或等价方式检查出 `test_accuracy`。
3. `test_contracts.py` 必须通过 AST 或等价方式检查出 `test_warmup_contract`。
4. `test_contracts.py` 不得通过 AST 或等价方式检查出其他 pytest `test_*` 函数。
5. 目标状态下不得继续新增 `test_accuracy.py` 或 `test_warmup.py` 旧入口。
6. `test_contracts.py` 不得包含 `for`、`if`、`try`、`with`，也不得定义两个固定测试函数之外的函数。
7. 结构不满足要求时，应在 pytest collection 或 import 阶段明确失败。

`test_accuracy` 调用共享后台数值对齐 runner。

`test_warmup_contract` 调用共享后台 warmup runner。

warmup 输入样本来自 `cases.py` 中的 `CASES`。

`IndicatorComparisonCase.warmup_check` 表达是否参与 warmup contract 校验，以及极特殊 skip 逃生舱。

要求：

1. 必须使用统一聚合函数 `resolve_indicator_contracts(...)` 作为全局 warmup 真值入口。
2. 不得另起一套 warmup 真值来源。
3. `cases.py` 不得声明自定义 `warmup_bars`、`warmup_mode` 或同类真值字段。
4. 运行时输出校验必须消费聚合函数返回的 `contract.warmup_bars` 与 `contract.warmup_mode`。
5. warmup skip 必须通过 `WarmupCheck.skip(...)` 显式表达。
6. warmup skip 必须写原因。
7. AI 使用 warmup skip 前必须报告用户并讨论。
8. 数值对齐 runner 不能消费 warmup skip 来改变数值对齐行为。

### `fixtures/`

只放该指标自己的本地 fixture。

`fixtures/local_csv/` 用于该指标的 local CSV oracle 或本地 CSV 数据。

## 4. 共享后台职责

`comparison/` 目录只承载通用框架。

### `case.py`

定义 case 数据结构、oracle 类型、skip 类型、tolerance 类型。

### `runner.py`

负责执行正式回测链路、调度 adapter、调度 oracle、调度比较与报错。

runner 必须通过 `run_indicator_backtest(...)` 或等价正式入口取得 engine 输出。

### `compare.py`

负责 strict exact comparison、全列缺失值 mask、布尔列逐点比较、数值列 `allclose`、comparison mismatch 类型。

`expected_different` 必须复用 same comparator，并精确识别 comparison mismatch。

### `datasets.py`

负责标准生成数据与本地 CSV 数据加载。

数据来源类型固定为：

```python
DatasetId | Path
```

`DatasetId` 表示一个具体的标准生成数据集。

`Path` 表示本地 CSV 数据文件。

`CASES` 必须在 `cases.py` 中列出可直接参数化的最终 case。

默认每个指标先声明 3 个标准 case，每个 case 绑定一组参数和一个具体 `DatasetId`。

每个 dataset 必须对应一个独立 pytest item。

runner 只执行传入的单个 case，不得在单个 pytest case 内部循环展开多个 dataset。

### `reporting.py`

负责失败上下文输出。

失败信息必须包含校验模式、指标、列、行、参数、数据源、oracle 和短上下文。

### `oracle_types.py`

定义 pandas-ta、pandas-ta-classic、local_csv 等 oracle 声明类型。

`LocalCsvOracle` 不暴露重复 `path` 或 `similarity_api`。

### `test_global_warmup_contracts.py`

承载全局 warmup 冻结项。

它不属于单指标目录。

它负责保留：

1. `resolve_indicator_contracts(...)` 静态契约检查。
2. warmup scaling scan。
3. 布尔 `False` 不被 Strict 缺失检查误杀的回归检查。

单指标目录的 `test_warmup_contract` 只负责消费该指标 `CASES` 派生出的静态和运行时 warmup 校验。

## 5. 新增指标需要修改的文件

普通指标新增测试时，默认只新增或修改：

```text
py_entry/Test/indicators/<indicator>/cases.py
py_entry/Test/indicators/<indicator>/adapter.py
py_entry/Test/indicators/<indicator>/test_contracts.py
```

如果使用本地 CSV，再新增：

```text
py_entry/Test/indicators/<indicator>/fixtures/local_csv/*.csv
```

不应修改共享后台，除非新增的是通用能力。

## 6. 审查口径

审查新增指标时，优先看该指标目录。

需要确认：

1. 指标目录是否包含该指标全部扩展内容。
2. adapter 是否只做取数与格式转换。
3. engine 输出是否仍来自正式回测链路。
4. case 是否没有内联 warmup 数值真值。
5. warmup skip 是否只通过 `WarmupCheck.skip(...)` 显式表达。
6. local CSV 数据来源是否使用 `Path`。
7. 共享后台是否没有被塞入指标特有逻辑。
8. `test_contracts.py` 是否固定只包含 `test_accuracy` 与 `test_warmup_contract`。
9. `test_contracts.py` 是否没有额外 pytest `test_*` 函数。
10. 是否默认声明 3 个参数和数据都不同的标准 case。
11. 全局 warmup 冻结项是否仍由共享全局测试承载。
12. 硬结构校验是否覆盖指标目录入口文件缺失、函数缺失、多余函数与旧入口残留。
