# 默认行为与特殊处理

## 1. 默认行为

默认行为是测试系统的主干，执行时不需要额外解释。

默认行为包括：

1. engine 输出来自 Rust 回测引擎的正式 `ResultPack.indicators`。
2. oracle 输入复用同一次执行得到的同一个 `DataPack.source`。
3. manifest 使用本项目回测引擎命名风格。
4. 普通指标默认声明 3 个标准 case，每个 case 使用不同参数和不同 `DatasetId`。
5. 主校验源由用户在 case 中显式声明。
6. 前四级 pandas-ta / pandas-ta-classic 校验源只使用 strict exact。
7. strict exact 检查长度、列、缺失值 mask 位置、布尔值和数值 `allclose`。
8. secondary assertion 只用于 pandas-ta / pandas-ta-classic 四级 oracle 路线，复用 same comparator，且 expected different 只精确识别 comparison mismatch。
9. warmup contract 默认由 warmup 专用测试执行，`resolve_indicator_contracts(...)` 是全局真值入口，comparison case 不承载 warmup 数值真值。
10. pytest 输出必须清楚显示指标、参数、数据集、校验源和失败位置。
11. case、adapter、oracle、dataset、skip、tolerance 与 adapter 回调边界使用 Pydantic 严格模型，并配合静态类型标注。

## 2. 特殊处理

特殊处理必须谨慎。

凡是使用特殊处理，都必须写注释；AI 使用前必须报告用户并讨论。

特殊处理清单：

1. 选择低于项目优先级最高可用项的主校验源。
2. 使用 `pandas-ta-classic`。
3. 使用 `local_csv`。
4. 使用 `local_csv similarity`。
5. 对某个指标或某列放宽容差。
6. 只校验部分输出列。
7. 跳过整个 case。
8. 跳过某个输出列。
9. 跳过 warmup contract。
10. 使用非标准生成数据集。
11. 使用本地 CSV fixture。
12. 增加除默认相关性 API 外的额外 similarity 指标。

## 3. Skip 规则

默认不允许 skip。

skip 只允许两种作用域：

1. `case`：跳过整个 case。
2. `output`：跳过某个输出列。

跳过某个输出列时，其他输出列仍必须正常校验。

warmup skip 是独立特殊处理，也是逃生舱；只能通过 `WarmupCheck.skip(...)` 显式声明，只由 warmup runner 消费，不由 comparison case skip 隐式触发。

所有 skip 都必须使用显式 pytest skip 或 manifest skip 标记，并写明原因。

禁止静默跳过，禁止通过注释删除 case 或输出列来隐藏跳过。
