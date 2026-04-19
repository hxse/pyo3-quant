# Strict Exact Comparison Contract

## 1. 适用范围

以下 oracle 必须使用 strict exact comparison：

1. `pandas_ta_talib_true_exact`
2. `pandas_ta_talib_false_exact`
3. `pandas_ta_classic_talib_true_exact`
4. `pandas_ta_classic_talib_false_exact`

## 2. 通过条件

strict exact comparison 必须同时满足：

1. engine 与 oracle 长度一致。
2. 输出列映射完整。
3. 缺失值 mask 完全一致，包括数量和位置。
4. 布尔列逐点相等。
5. 数值列在有效位置逐点 `allclose`。
6. 容差默认为当前全局 `rtol=1e-5`、`atol=1e-8`。
7. 允许对特定指标、特定输出列声明更宽容差，但必须在 case 附近用注释说明原因。

## 3. 缺失值规则

缺失值规则必须同时处理 `null` 与 `NaN`。

strict exact comparison 不只检查前导缺失数量，也必须检查全列缺失位置。

如果某指标存在结构性内部缺失，必须在指标 case 中显式声明，并说明该结构性缺失是否属于正式输出语义。

## 4. 禁止项

strict exact comparison 禁止：

1. 用 correlation 作为通过条件。
2. 用方向一致率作为通过条件。
3. 只比较最后 N 行。
4. 自动裁剪 warmup 外的额外区间。
5. oracle 失败后自动换下一级 oracle。
6. 给前四级 oracle 暴露 similarity 比较入口。

任何裁剪、列跳过、容差放宽都必须显式写在 case 或就近注释中。

## 5. 实现方式约束

exact comparison 应优先复用或最小增强当前比较工具。

数值比较使用 `numpy.testing.assert_allclose`。

布尔和 mask 比较使用 `numpy.testing.assert_array_equal` 或等价的 pandas / polars 内置比较 API。

不得为基础数组比较手写一套新算法。
