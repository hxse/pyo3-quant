# KC Legacy Kill List

## 1. 禁止残留

KC 完成时不得残留：

1. 运行时外部 KC 计算。
2. 运行时外部 EMA / TR 计算后拼装 KC。
3. 使用独立 `atr` 指标近似 KC 通道宽度。
4. `period` 参数别名。
5. `basis` 与 `middle` 双输出。
6. `pandas-ta-classic` 默认基准。
7. 绕过 registry 的局部 KC 调用。

## 2. 最终扫描范围

```text
src/backtest_engine/indicators
src/backtest_engine/indicators/registry.rs
src/backtest_engine/indicators/mod.rs
py_entry/Test/indicators
py_entry
python/pyo3_quant
```

## 3. 残留处理

若发现未确认归属的工作区残留，不得静默修改。必须在 review 中报告，由人工确认是否纳入清理。
