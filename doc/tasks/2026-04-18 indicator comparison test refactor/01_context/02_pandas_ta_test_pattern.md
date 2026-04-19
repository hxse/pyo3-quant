# pandas-ta 测试模式参考

## 1. 参考来源

参考目录：

```text
https://github.com/hxse/pandas-ta/tree/development/tests
```

代表文件：

```text
tests/config.py
tests/conftest.py
tests/test_indicator_momentum.py
tests/test_indicator_overlap.py
tests/test_indicator_trend.py
tests/test_indicator_volatility.py
```

## 2. 主要模式

`pandas-ta` 按指标类别拆分测试文件，例如 momentum、overlap、trend、volatility、volume。

共享测试数据通过 fixture 提供。指标测试一般覆盖两类入口：

1. 标准函数调用：`ta.xxx(...)`。
2. DataFrame extension 调用：`df.ta.xxx(append=True)`。

每个指标通常至少检查：

1. 返回类型是 `Series` 或 `DataFrame`。
2. `result.name` 是否符合预期。
3. 追加到 DataFrame 的输出列名是否符合预期。
4. 若存在 TA-Lib 对应实现，则尝试与 TA-Lib 输出精确比较。
5. 精确比较失败时，部分测试用相关性阈值作为后备诊断或通过条件。

## 3. 可借鉴内容

可以借鉴：

1. 每个指标显式检查返回类型、名称、输出列。
2. 对多输出指标逐列解析和逐列比较。
3. 对特殊指标使用单独样本或特殊裁剪规则。
4. 对同一指标覆盖默认参数和特殊参数模式。

不采用“按指标类别或形态组织测试文件”作为本任务目标。

目标结构继续按单指标组织，但从平铺单文件收口为单指标目录，便于 pytest 定位失败点，也便于集中放置该指标的 case、adapter、pytest contract 入口与 fixture。

## 4. 不可照搬内容

不能照搬：

1. 不能把原始 `talib` 作为本仓库正式真值源。
2. 不能把 correlation / similarity 用作 pandas-ta exact oracle 的默认通过条件。
3. 不能测试 DataFrame extension 入口；本仓库正式口径是 `import pandas_ta as ta; ta.xxx(...)`。
4. 不能为了覆盖面引入外部自定义指标链路。
5. 不能照搬相关性通过口径；`pandas-ta` 测试中使用的 `ta.utils.df_error_analysis(...)` 只能作为 local CSV similarity 的默认相关性 API 参考。
