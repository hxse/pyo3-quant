# 全局验证策略

## 1. 静态检查

每次新增或修改内置指标后，必须执行：

```bash
just check
```

## 2. 单指标测试

新增指标必须执行对应测试：

```bash
just test-py py_entry/Test/indicators/test_<base_name>.py
```

## 3. warmup contract 测试

新增指标必须执行：

```bash
just test-py py_entry/Test/indicators/test_indicator_warmup_contract.py
```

## 4. 扩大回归

若修改了公共指标 helper、registry 行为、测试模板或 warmup 聚合逻辑，应执行：

```bash
just test-py py_entry/Test/indicators
```

## 5. 最终扫描

每个指标完成后必须扫描：

```bash
rg -n "<base_name>|相关英文名|相关中文名" src py_entry python
```

目的：

1. 确认正式实现只存在于内置指标系统和测试中。
2. 确认没有运行时外部自定义指标路径。
3. 确认没有错误真值源残留。
