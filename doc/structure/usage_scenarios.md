# Backtest 使用速查

## 快速回测
```python
from py_entry.runner import Backtest

bt = Backtest(data_source=...)
result = bt.run()
print(result.summary.performance)
```

## 回测图表（Notebook）
```python
from py_entry.runner import FormatResultsConfig
from py_entry.io import DisplayConfig

result = bt.run()
result.format_for_export(FormatResultsConfig(dataframe_format="csv"))
result.display(config=DisplayConfig(embed_data=False))
```

## 导出与保存
```python
from py_entry.runner import FormatResultsConfig

result = bt.run()
result.format_for_export(FormatResultsConfig(dataframe_format="csv"))
result.save(...)
# result.upload(...)
```

## 全局优化
```python
opt = bt.optimize(opt_cfg)
print(opt.optimize_metric, opt.optimize_value, opt.total_samples, opt.rounds)
```

## 参数抖动
```python
sens = bt.sensitivity(sens_cfg)
print(sens.target_metric, sens.mean, sens.std, sens.cv)
```

## 向前测试
```python
wf = bt.walk_forward(wf_cfg)
print(wf.aggregate_test_metrics)
print(wf.best_window_id, wf.worst_window_id)
```

## WF 图表（拼接 OOS）
```python
from py_entry.io import DisplayConfig

wf = bt.walk_forward(wf_cfg)
wf.display(config=DisplayConfig(embed_data=False))
```

## 安全串行（关键）
```python
result = bt.run()
result.format_for_export(...)
result.display(...)
opt = bt.optimize(opt_cfg)  # 可直接继续，不会触发 duplicate index
```

## private 实战速查（CLI）
```bash
just run example_strategy backtest
just run example_strategy optimize
just run example_strategy sensitivity
just run example_strategy walk_forward
just run example_strategy pipeline
```

## private 实战速查（Notebook）
```python
from py_entry.private_strategies.template import run_stage

STRATEGY = "example_strategy"

backtest_result = run_stage(STRATEGY, "backtest")
opt_result = run_stage(STRATEGY, "optimize")
sens_result = run_stage(STRATEGY, "sensitivity")
wf_result = run_stage(STRATEGY, "walk_forward")
```

## 说明
- `format_for_export(...)` 只在导出副本上处理，不污染计算态数据。
- AI 优先跑 `.py`/CLI；人类优先看 `ipynb` 图表。
- 参见：`AGENTS.md`、`doc/structure/strategy_cross_module_plan.md`。
