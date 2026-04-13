# 阶段验收

## 1. Stage 1: Pack Producer 收口

### 1.1 验收结论

本阶段验收通过。

### 1.2 已验收事实

1. `DataPack` / `ResultPack` 的 Python stubs 已移除公开 `__new__` 与 setter。
2. `active_extract.rs`、`slicing.rs` 已不再直接手造正式 pack，而是回到 `build_data_pack(...)` / `build_result_pack(...)`。
3. `test_top_level_api_validation.py`、`test_backtest_regression_guards.py` 等契约测试已迁移到 producer 真值入口口径。
4. 生产代码中的 pack 构造真值已收口到 `build_data_pack(...)`、`build_result_pack(...)`、`extract_active(...)`。

### 1.3 对应材料

1. `src/backtest_engine/data_ops/active_extract.rs`
2. `src/backtest_engine/data_ops/slicing.rs`
3. `python/pyo3_quant/_pyo3_quant/__init__.pyi`
4. `py_entry/Test/backtest/common_tests/test_top_level_api_validation.py`

## 2. Stage 2: 执行层主链重构

### 2.1 验收结论

本阶段验收通过。

### 2.2 已验收事实

1. `ExecutionStage` 已收口为 `Indicator / Signals / Backtest / Performance`，`ArtifactRetention` 已进入正式公开设置。
2. 内部执行主链已收口为 `PipelineRequest -> execute_single_pipeline(...) -> PipelineOutput`。
3. `run_backtest_engine(...)` / `py_run_backtest_engine(...)` 已退出正式入口，收口为 `run_batch_backtest(...)` / `py_run_batch_backtest(...)`。
4. `BacktestContext` 与 `utils/context.rs` 已退出执行主链。
5. optimizer / sensitivity 已统一通过 `evaluate_param_set(...)` 复用 single pipeline 语义。

### 2.3 对应材料

1. `src/backtest_engine/pipeline/mod.rs`
2. `src/backtest_engine/pipeline/executor.rs`
3. `src/backtest_engine/pipeline/tests.rs`
4. `src/backtest_engine/top_level_api.rs`
5. `src/backtest_engine/mod.rs`
6. `src/backtest_engine/optimizer/runner/mod.rs`
7. `src/backtest_engine/sensitivity/runner.rs`

## 3. Stage 3: 模式调用面与外围链路收束

### 3.1 验收结论

本阶段验收通过。

### 3.2 已验收事实

1. Python precheck `validate_wf_indicator_readiness(...)` 已删除，workflow 已直接进入正式入口。
2. Python runner 已收口为 `Backtest + RunnerSession + *View + PreparedExportBundle` 四层。
3. `display/save/upload` 已改为正式消费 `PreparedExportBundle`。
4. single / WF 已改为 `prepare_export(...)`，WF stitched 不再伪装 single 结果视图。
5. source time / stitched time 已收口为严格递增，Renko 已退出正式入口、正式源码树、配置面、测试构造与测试辅助示例口径。

### 3.3 对应材料

1. `py_entry/runner/backtest.py`
2. `py_entry/runner/results/__init__.py`
3. `py_entry/runner/results/_export_pipeline.py`
4. `py_entry/runner/display/__init__.py`
5. `src/backtest_engine/walk_forward/window_runner.rs`
6. `src/backtest_engine/walk_forward/stitch.rs`
7. `src/backtest_engine/walk_forward/stitched_checks.rs`

## 4. Stage 4: 最终清扫与回归

### 4.1 验收结论

本阶段验收通过。

### 4.2 已验收事实

1. `just check` 已通过。
2. `just test` 已通过，结果为 `597 passed, 45 skipped`。
3. `test_runner_view_contracts.py` 已收口 typed fake raw，`WalkForwardView / OptimizationView / SensitivityView` 的正式 raw 注解与测试边界一致，`just check` 不再报 `invalid-argument-type`。
4. `WalkForwardView.stitched_equity` 已改为 schema 漂移直接报错，缺少 `equity` 列时不再静默返回空数组。
5. Python `Backtest` 门面已显式编译 WF / optimizer / sensitivity / Optuna 各自要求的正式 mode settings，strategy_hub demo 的模式调用路径已通过回归验证。
6. `RunnerSession.engine_settings` 已收口为执行时快照，已返回 view 不会被后续 `Backtest.engine_settings` mutation 污染。
7. 公开面旧名字自动化护栏测试已补齐，Legacy Kill List 关键字扫描结果已沉淀在 `03_fix_log.md`。
