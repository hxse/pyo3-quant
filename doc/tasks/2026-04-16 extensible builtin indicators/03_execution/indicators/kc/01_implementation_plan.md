# KC 实现计划

## 1. 新增文件

```text
src/backtest_engine/indicators/kc/config.rs
src/backtest_engine/indicators/kc/expr.rs
src/backtest_engine/indicators/kc/pipeline.rs
src/backtest_engine/indicators/kc/indicator.rs
src/backtest_engine/indicators/kc/mod.rs
py_entry/Test/indicators/test_kc.py
```

## 2. 修改文件

```text
src/backtest_engine/indicators/mod.rs
src/backtest_engine/indicators/registry.rs
py_entry/Test/indicators/test_indicator_warmup_contract.py
```

## 3. 模块职责

`config.rs`：

1. 定义 `KCConfig`。
2. 保存 `length / scalar`。
3. 保存输入列名和输出列名。

`expr.rs`：

1. 构造 True Range 表达式。
2. 构造 `EMA(close, length)`。
3. 构造 `EMA(True Range, length)`。
4. 构造 `lower / middle / upper`。

`pipeline.rs`：

1. 提供 `kc_lazy(...)`。
2. 提供 `kc_eager(...)`。
3. 做参数合法性和数据长度检查。

`indicator.rs`：

1. 实现 `Indicator` trait。
2. 读取 `length / scalar`。
3. 绑定输出列名。
4. 声明 warmup。

## 4. 不做事项

1. 不实现外部自定义指标入口。
2. 不添加 `period` 参数别名。
3. 不开放 `tr` 或 `mamode`。
4. 不复用当前独立 `atr` 指标作为 KC 通道宽度。
