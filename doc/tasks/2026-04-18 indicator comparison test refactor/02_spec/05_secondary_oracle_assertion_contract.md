# Secondary Oracle Assertion Contract

## 1. 定义

secondary oracle assertion 用于在主校验源之外，再对另一个 oracle 做附加断言。

它支持两种期望：

1. `expected_same`
2. `expected_different`

`expected_different` 对应此前讨论的“不一致校验”，但实现上不新增独立 diff comparator。

## 2. 使用场景

项目推崇的 pandas-ta 对齐风格是双重校验：

1. 如果主校验源是 `pandas-ta (talib=true)`，应尽量再校验 `pandas-ta (talib=false)` 是 same 还是 different。
2. 如果主校验源是 `pandas-ta (talib=false)`，应尽量再校验 `pandas-ta (talib=true)` 是 same 还是 different。

这样可以同时确认“对齐了正确路径”和“没有误对齐到另一条路径”。

## 3. 校验方式

secondary assertion 只用于 pandas-ta / pandas-ta-classic 四级 oracle 路线。

它用于确认当前实现对齐了某个 pandas-ta 路径，同时没有误对齐到另一个 pandas-ta 路径。

`local_csv` 是后备交叉验证路线，不参与 secondary assertion。

当主校验源是 `local_csv`，无论 `compare_mode` 是 `exact` 还是 `similarity`，都不得声明 secondary oracle assertion。

secondary assertion 的校验模式必须自动复用 strict exact 逻辑。

用户只声明目标 oracle 与期望，不声明另一套比较模式。

`expected_same` 直接调用 same comparator。

`expected_different` 不发明新比较逻辑，而是调用同一个 same comparator，并精确识别其比较失败：

1. same comparator 返回结构化 mismatch，或抛出专用 comparison mismatch 异常，说明确实 different。
2. same comparator 判定通过，说明不满足 expected different，测试失败。
3. extractor、oracle 加载、参数转换、列解析、数据源读取等非比较失败，必须原样冒泡，不得被当成 expected different 通过。

禁止使用宽泛捕获：

```python
except Exception
except AssertionError
```

禁止通过异常消息字符串判断是否为 expected different 通过条件。

如果现有 same comparator 只会抛出 `AssertionError`，重构时必须先把 same comparator 的失败语义拆成可精确识别的结构化结果或专用异常，再实现 expected different。

## 4. 作用范围

默认作用范围是全部输出列。

允许指定输出列。

指定输出列时：

1. 指定列必须满足 `expected_same` 或 `expected_different`。
2. 未指定列仍必须 `expected_same`。
3. 不允许因为指定了部分列就跳过其他列。

## 5. different 判定

`expected_different` 只保留两级能力：

1. 整体输出不同。
2. 指定列不同。

不设计区间级、初始化段级 negative 断言，避免过度设计。
