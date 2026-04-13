# Backtest 使用速查

## 快速回测
```python
from py_entry.runner import Backtest

bt = Backtest(data_source=...)
result = bt.run()
print(result.raw.performance)
```

## 回测图表（Notebook）
```python
from py_entry.runner import FormatResultsConfig
from py_entry.io import DisplayConfig

result = bt.run()
bundle = result.prepare_export(FormatResultsConfig(dataframe_format="csv"))
bundle.display(config=DisplayConfig(embed_data=False))
```

## 导出与保存
```python
from py_entry.runner import FormatResultsConfig

result = bt.run()
bundle = result.prepare_export(FormatResultsConfig(dataframe_format="csv"))
bundle.save(...)
# bundle.upload(...)
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
bundle = wf.prepare_export(...)
bundle.display(config=DisplayConfig(embed_data=False))
```

## 安全串行（关键）
```python
result = bt.run()
bundle = result.prepare_export(...)
bundle.display(...)
opt = bt.optimize(opt_cfg)  # 可直接继续，不会触发 duplicate index
```

## private 实战速查（CLI）
```bash
just workflow --strategies sma_2tf --symbols SOL/USDT --mode backtest
just workflow --strategies sma_2tf --symbols SOL/USDT --mode optimize
just workflow --strategies sma_2tf --symbols SOL/USDT --mode sensitivity
just workflow --strategies sma_2tf --symbols SOL/USDT --mode walk_forward
just workflow --strategies sma_2tf --symbols SOL/USDT --mode backtest,optimize,sensitivity,walk_forward
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
wf_result = bt.walk_forward(stage_cfgs["wf_cfg"])
```

## 说明
- `prepare_export(...)` 只在导出副本上处理，不污染计算态数据。
- WF fail-fast 真值统一回到 Rust 正式入口，不再保留 Python precheck gate。
- AI 优先跑 `.py`/CLI；人类优先看 `ipynb` 图表。
- 参见：`AGENTS.md`、`doc/structure/strategy_cross_module_plan.md`。
