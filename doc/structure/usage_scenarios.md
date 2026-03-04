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
precheck = bt.validate_wf_indicator_readiness(wf_cfg)
print(precheck["effective_transition_bars"])

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
just run strategy=sma_2tf mode=backtest
just run strategy=sma_2tf mode=optimize
just run strategy=sma_2tf mode=sensitivity
just run strategy=sma_2tf mode=walk_forward
just run strategy=sma_2tf mode=pipeline
```

## private 实战速查（Notebook）
```python
from py_entry.strategy_hub import build_strategy_runtime

STRATEGY = "search:sma_2tf.sma_2tf"
RUN_SYMBOL = "SOL/USDT"

spec, stage_cfgs, bt = build_strategy_runtime(STRATEGY, run_symbol=RUN_SYMBOL)

backtest_result = bt.run()
opt_result = bt.optimize(stage_cfgs["opt_cfg"])
sens_result = bt.sensitivity(stage_cfgs["sens_cfg"])
bt.validate_wf_indicator_readiness(stage_cfgs["wf_cfg"])
wf_result = bt.walk_forward(stage_cfgs["wf_cfg"])
```

## 说明
- `format_for_export(...)` 只在导出副本上处理，不污染计算态数据。
- WF 推荐显式先跑一次 `validate_wf_indicator_readiness(...)`，失败直接中断。
- AI 优先跑 `.py`/CLI；人类优先看 `ipynb` 图表。
- 参见：`AGENTS.md`、`doc/structure/strategy_cross_module_plan.md`。
