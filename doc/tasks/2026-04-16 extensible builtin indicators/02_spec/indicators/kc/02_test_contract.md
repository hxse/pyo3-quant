# KC 测试契约

## 1. 准确性测试

新增：

```text
py_entry/Test/indicators/test_kc.py
```

测试使用现有 `IndicatorTestConfig` 与 `validate_indicator_accuracy(...)`。

## 2. pandas-ta 基准

基准调用：

```python
ta.kc(
    high=df["high"],
    low=df["low"],
    close=df["close"],
    length=length,
    scalar=scalar,
    tr=True,
    mamode="ema",
)
```

KC 在原版 `pandas-ta` 中存在，因此不后退到 `pandas-ta-classic`。

## 3. 输出列提取

engine extractor 提取：

```text
<indicator_key>_lower
<indicator_key>_middle
<indicator_key>_upper
```

pandas-ta extractor 映射：

```text
KCL... -> lower
KCB... -> middle
KCU... -> upper
```

## 4. 参数覆盖

至少覆盖：

```text
ohlcv_15m:
  kc_0: length=20, scalar=2.0
  kc_1: length=14, scalar=1.5

ohlcv_1h:
  kc_0: length=20, scalar=2.0
  kc_1: length=30, scalar=2.5
```

## 5. warmup contract 测试

在 `test_indicator_warmup_contract.py` 中新增：

```text
("kc", {"length": Param(20), "scalar": Param(2.0)}, 20, "Strict")
```

## 6. warmup 缩放测试

在 warmup scaling scan 中加入：

```text
("kc", "length", [1, 5, 50, 200])
```

构造参数时补充：

```text
scalar = Param(2.0)
```
