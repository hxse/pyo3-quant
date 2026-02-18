# Backtest 使用场景（当前版）

本文档描述当前 `Backtest` 的推荐使用方式。

## 1. 快速验证

```python
from py_entry.runner import Backtest

bt = Backtest(data_source=...)
result = bt.run()
result.display()
```

适合：检查策略是否跑通、查看基本图表。

## 2. 正式回测与导出

```python
from py_entry.runner import FormatResultsConfig

result = bt.run()
result.format_for_export(FormatResultsConfig(dataframe_format="csv"))
result.save(...)
# result.upload(...)  # 按需
result.display()
```

适合：落盘归档、对外分享结果。

## 3. 参数优化

```python
opt = bt.optimize()
print(opt.best_params)
```

适合：在给定参数空间中搜索更优组合。

## 4. 优化后复跑

```python
opt = bt.optimize()
final = bt.run(params_override=opt.best_params)
final.display()
```

适合：查看最优参数下的完整曲线与明细。

## 5. Walk Forward

```python
wf = bt.walk_forward()
print(wf.aggregate_test_metrics)
```

适合：检查参数在滚动窗口中的稳健性。

## 6. 敏感性分析

```python
sens = bt.sensitivity()
print(sens)
```

适合：评估参数扰动后的稳定程度。

## 7. Notebook 交互探索

- notebook 负责参数切换、图表展示
- 策略实现放在 `.py`，通过 `run_xxx()` 导入调用
- 不建议在 notebook 中堆核心策略逻辑

## 8. AI 与人类的职责分层

- AI 默认运行 `.py` 脚本并读取 `__main__` 输出
- 人类主要查看 `ipynb` 图表
- AI 默认不直接读取 `ipynb`，除非明确指令

参见：`AGENTS.md`、`doc/structure/strategy_cross_module_plan.md`
