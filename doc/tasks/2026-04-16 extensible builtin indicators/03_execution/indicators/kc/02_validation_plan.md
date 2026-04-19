# KC 验证计划

## 1. 静态检查

```bash
just check
```

## 2. KC 准确性测试

```bash
just test-py py_entry/Test/indicators/test_kc.py
```

预期：

1. `lower / middle / upper` 与原版 `pandas-ta` 对齐。
2. 覆盖 `ohlcv_15m` 与 `ohlcv_1h`。
3. 覆盖多组 `length / scalar`。

## 3. warmup contract 测试

```bash
just test-py py_entry/Test/indicators/test_indicator_warmup_contract.py
```

预期：

1. `kc` warmup 为 `length`。
2. `kc` mode 为 `Strict`。
3. `length` 缩放扫描单调不减。

## 4. 扩大回归

若实现过程中触碰公共指标逻辑，追加：

```bash
just test-py py_entry/Test/indicators
```
