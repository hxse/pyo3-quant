# 文件修改清单

## 1. Rust pack producer 与 pack 类型

这一组负责落实“禁止绕过工具函数构建 pack”：

1. `src/backtest_engine/data_ops/data_pack_builder.rs`
2. `src/backtest_engine/data_ops/result_pack_builder.rs`
3. `src/backtest_engine/data_ops/active_extract.rs`
4. `src/backtest_engine/data_ops/slicing.rs`
5. `src/backtest_engine/data_ops/source_contract.rs`
6. `src/backtest_engine/data_ops/mod.rs`
7. `src/backtest_engine/data_ops/fetch_planner/planner.rs`
8. `src/types/inputs/data.rs`
9. `src/types/outputs/backtest.rs`
10. `python/pyo3_quant/_pyo3_quant/__init__.pyi`
11. `python/pyo3_quant/backtest_engine/data_ops/__init__.pyi`

## 2. 执行层主链与公开设置

这一组负责落实 `stop_stage / artifact_retention`、`execute_single_pipeline(...)`、`BacktestContext` 删除、`run_backtest_engine(...) -> run_batch_backtest(...)` 改名与命名分层：

1. `src/types/inputs/settings.rs`
2. `src/backtest_engine/top_level_api.rs`
3. `src/backtest_engine/mod.rs`
4. `src/backtest_engine/utils/context.rs`
5. `src/backtest_engine/utils/mod.rs`
6. `src/backtest_engine/utils/memory_optimizer.rs`
7. `src/backtest_engine/module_registry.rs`
8. `python/pyo3_quant/_pyo3_quant/__init__.pyi`
9. `python/pyo3_quant/backtest_engine/__init__.pyi`

本轮实际拆分为 `src/backtest_engine/pipeline/` 目录：

1. `src/backtest_engine/pipeline/mod.rs`
2. `src/backtest_engine/pipeline/types.rs`
3. `src/backtest_engine/pipeline/settings.rs`
4. `src/backtest_engine/pipeline/public_result.rs`
5. `src/backtest_engine/pipeline/validation.rs`
6. `src/backtest_engine/pipeline/executor.rs`
7. `src/backtest_engine/pipeline/tests.rs`

## 3. WF / optimizer / sensitivity 调用面

这一组负责把各模式拉回同一条内部执行主链：

1. `src/backtest_engine/walk_forward/runner.rs`
2. `src/backtest_engine/walk_forward/window_runner.rs`
3. `src/backtest_engine/walk_forward/stitch.rs`
4. `src/backtest_engine/optimizer/runner/mod.rs`
5. `src/backtest_engine/optimizer/evaluation.rs`
6. `src/backtest_engine/optimizer/mod.rs`
7. `src/backtest_engine/sensitivity/runner.rs`

## 4. Python runner wrapper 与公开入口

这一组负责落实 `RunnerSession`、统一 `*View` 命名、`PreparedExportBundle` 与旧 wrapper 退出：

1. `py_entry/runner/__init__.py`
2. `py_entry/runner/backtest.py`
3. `py_entry/runner/results/__init__.py`
4. `py_entry/runner/results/run_result.py`
5. `py_entry/runner/results/batch_result.py`
6. `py_entry/runner/results/wf_result.py`
7. `py_entry/runner/results/opt_result.py`
8. `py_entry/runner/results/sens_result.py`
9. `py_entry/runner/results/optuna_result.py`
10. `py_entry/runner/diagnostics.py`
11. `py_entry/runner/display/__init__.py`
12. `py_entry/runner/display/html_renderer.py`
13. `py_entry/runner/display/widget_renderer.py`
14. `py_entry/runner/display/marimo_renderer.py`
15. `py_entry/io/result_export.py`

若实现中采用新的 Python 结果层目录，预计新增：

1. `py_entry/runner/views/__init__.py`
2. `py_entry/runner/views/session.py`
3. `py_entry/runner/views/single_view.py`
4. `py_entry/runner/views/batch_view.py`
5. `py_entry/runner/views/walk_forward_view.py`
6. `py_entry/runner/views/optimization_view.py`
7. `py_entry/runner/views/sensitivity_view.py`
8. `py_entry/runner/views/optuna_view.py`
9. `py_entry/runner/export_bundle.py`

本组不是只改 adapter / packager。

必须同时覆盖下面三类迁移面：

1. 公开返回类型迁移：
   `Backtest.run / batch / walk_forward / optimize / sensitivity / optimize_with_optuna`
2. 旧 wrapper 文件迁移：
   旧 `results/*` 文件要么删除，要么退为纯内部实现细节；不得继续承担正式公开命名
3. Python 公开导出入口迁移：
   `format_for_export(...)` -> `prepare_export(...)`
   `display/save/upload` -> `PreparedExportBundle.display/save/upload`

## 5. Python 配置、序列化与结构文档

这一组负责落实旧字段迁移、公开 backtest 入口改名、precheck 删除、对外示例与 bundle 口径同步：

1. `py_entry/runner/setup_utils.py`
2. `py_entry/strategy_hub/core/config.py`
3. `py_entry/strategy_hub/core/executor.py`
4. `py_entry/scanner/strategies/_scan_backtest.py`
5. `py_entry/io/_converters_bundle.py`
6. `py_entry/types/__init__.py`
7. `doc/structure/pyo3_interface_design.md`
8. `doc/structure/python_api.md`
9. `doc/structure/usage_scenarios.md`
10. `doc/structure/multi_timeframe_data_integrity.md`

## 6. data generator / source time / Renko

这一组负责收口严格递增时间契约与 Renko 退出正式入口：

1. `py_entry/data_generator/data_generator.py`
2. `py_entry/data_generator/__init__.py`
3. `py_entry/data_generator/config.py`
4. `py_entry/data_generator/renko_generator.py`
5. `src/backtest_engine/walk_forward/stitched_checks.rs`
6. `src/backtest_engine/walk_forward/stitch.rs`

## 7. export / display

这一组负责收口 adapter / packager 分层：

1. `py_entry/io/_converters_bundle.py`
2. single export / display 适配层相关文件
3. WF export / display 适配层相关文件
4. 通用 packager / display 消费链相关文件

## 8. 主要测试与夹具

这一组必须同步迁移，否则 breaking 规则无法真正落地：

1. `py_entry/Test/shared/backtest_builders.py`
2. `py_entry/Test/backtest/common_tests/*`
3. `py_entry/Test/backtest/test_data_pack_contract.py`
4. `py_entry/Test/backtest/test_result_pack_contract.py`
5. `py_entry/Test/backtest/test_extract_active_contract.py`
6. `py_entry/Test/backtest/test_strip_indicator_time_columns_contract.py`
7. `py_entry/Test/execution_control/*`
8. `py_entry/Test/walk_forward/*`
9. `py_entry/Test/result_export/*`
10. `py_entry/Test/data_generator/*`
11. `py_entry/Test/optimizer_benchmark/*`
12. `py_entry/Test/sensitivity/*`
13. `py_entry/benchmark/*`

## 9. 必须特别关注的残留点

这些位置当前已知最容易漏改：

1. `src/backtest_engine/data_ops/active_extract.rs`
2. `src/backtest_engine/data_ops/slicing.rs`
3. `src/backtest_engine/walk_forward/window_runner.rs`
4. `src/backtest_engine/walk_forward/stitch.rs`
5. `src/backtest_engine/optimizer/evaluation.rs`
6. `src/backtest_engine/sensitivity/runner.rs`
7. `py_entry/runner/results/run_result.py`
8. `py_entry/runner/results/wf_result.py`
9. `py_entry/runner/display/__init__.py`
10. `py_entry/io/_converters_bundle.py`
11. `py_entry/Test/signal/utils/mapping_helpers.py`
12. `py_entry/Test/backtest/common_tests/test_top_level_api_validation.py`
13. `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`
