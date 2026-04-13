# `03-10` 之后的残余基线

本文件只做一件事：记录当前 task 启动时，已经确认存在的残余事实。

它不替代 `02_spec`，也不替代 `Legacy Kill List`；它只是执行前的基线。

## 1. Python precheck 残余

1. `py_entry/runner/backtest.py` 仍公开 `validate_wf_indicator_readiness(...)`。
2. `py_entry/strategy_hub/core/executor.py` 仍显式调用该入口。
3. `doc/structure/python_api.md`、`doc/structure/usage_scenarios.md` 仍把它写成公开 API / 推荐步骤。
4. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`、`test_wf_ignore_indicator_warmup_contract.py`、`test_wf_signal_injection_contract.py`、`py_entry/Test/strategy_hub/test_strategy_hub_precheck_entrypoints.py` 仍围绕旧入口构造。

## 2. WF 导出残余

1. `py_entry/runner/results/run_result.py` 仍持有 `export_params`、`backtest_schedule` 和 `_USE_DEFAULT_EXPORT_PARAMS`。
2. `py_entry/runner/results/wf_result.py` 仍通过 stitched 结果包装 `RunResult` 再复用导出。
3. `py_entry/io/_converters_bundle.py` 仍直接理解 `backtest_schedule`。
4. `py_entry/runner/display/*` 当前仍把 `RunResult` 当正式 display 输入类型。

## 3. Python wrapper 残余

1. `py_entry/runner/results/run_result.py` 同时承担 single 结果视图、导出副本构造、bundle 缓存和 display/save/upload 会话。
2. `py_entry/runner/results/batch_result.py` 仍保存 `context: dict`，再临时拼回 `RunResult`。
3. `py_entry/runner/results/wf_result.py` 仍保存 `context: dict`，并惰性构造 stitched `RunResult` 代理。
4. `py_entry/runner/results/sens_result.py` 仍保留 `Wrapper` 命名，并通过 `__getattr__` 透传原始 Rust 对象。
5. `py_entry/runner/results/opt_result.py`、`sens_result.py`、`optuna_result.py` 当前命名不统一，分别使用 `Result / Wrapper / OptResult` 三套口径。
6. `py_entry/runner/__init__.py` 公开面当前仍直接导出这些风格不一致的 wrapper 名字。

## 4. 重复时间戳 / Renko 残余

1. `py_entry/data_generator/config.py` 仍保留 `renko_timeframes`。
2. `py_entry/data_generator/data_generator.py` 仍生成 `renko_*` source。
3. `py_entry/data_generator/__init__.py` 仍导出 `generate_renko / calculate_renko`。
4. `src/backtest_engine/walk_forward/stitched_checks.rs` 仍保留 `assert_source_times_non_decreasing(...)`。
5. `doc/structure/multi_timeframe_data_integrity.md` 仍保留“非递减（允许相等）”旧措辞。
6. `py_entry/Test/data_generator/test_generate_data_pack_integration.py` 仍把 Renko 入口当作重复时间戳拒绝测试载体。
7. `py_entry/Test/signal/test_signal_generation.py` 仍显式传 `renko_timeframes=None`。
8. `py_entry/Test/signal/utils/mapping_helpers.py`、`py_entry/Test/signal/utils/data_helpers.py` 的注释 / 示例仍把 `renko_*` 当正式 source 示例。

## 5. Context 残余

1. `src/backtest_engine/utils/context.rs` 仍存在 `BacktestContext`。
2. `src/backtest_engine/walk_forward/window_runner.rs` 仍通过 `BacktestContext` 承担局部 backtest / performance 执行。
3. 当前命名仍在暗示“通用执行上下文”，与其真实用途不符。
4. 当前对象只在 `window_runner` 使用，却仍挂在 `utils` 下，物理归属也在误导阅读者。

## 6. pack 构造现状

1. Python 公开面当前仍允许直接 `DataPack(...)` / `ResultPack(...)`。
2. Python stubs 当前仍公开这两个对象的 setter。
3. Rust 生产代码里仍有 `extract_active(...)`、`slice_result_pack(...)` 这类旁路直接使用 `new_checked(...)`。
4. 本任务需要先冻结“pack object 只能由 formal producer 产出”的边界，再进入代码执行。
