# 验证与测试计划

## 1. 验证顺序

本任务按仓库统一顺序验证：

1. 先做旧痕迹与调用面扫描
2. 再更新 stubs
3. 再执行 `just check`
4. 最后执行 `just test`

不在实现过程中反复穿插正式校验。

## 2. 实现前后都要跑的扫描

### 2.1 pack producer 扫描

至少扫描：

1. `DataPack::new_checked`
2. `ResultPack::new_checked`
3. `DataPack(`
4. `ResultPack(`
5. `extract_active(`
6. `slice_result_pack`

目标是确认：

1. 生产代码中的 pack 旁路构造是否清零
2. Python 公开 direct constructor 是否清零
3. 只允许 producer 真值入口，或纯参数整理后立即强制委托到 producer 真值入口且不新增对象级合法性语义的 delegator 保留

### 2.2 旧字段 / 旧控制流扫描

至少扫描：

1. `execution_stage`
2. `return_only_final`
3. `BacktestContext`
4. `execute_single_backtest`
5. `run_backtest_engine`
6. `py_run_backtest_engine`
7. `validate_wf_indicator_readiness`
8. `skip_validation`

### 2.3 Python wrapper / bundle 扫描

至少扫描：

1. `RunResult`
2. `BatchResult`
3. `WalkForwardResultWrapper`
4. `OptimizeResult`
5. `SensitivityResultWrapper`
6. `OptunaOptResult`
7. `format_for_export(`
8. `context={`
9. `__getattr__(`
10. `run_result`

目标是确认：

1. 旧 wrapper 命名是否清零
2. `format_for_export(...)` 是否已退出正式入口
3. `context: dict` 是否已退出 Python 结果层
4. `WalkForwardView` 是否不再保留 `run_result` 代理
5. `PreparedExportBundle` 是否成为 display/save/upload 的唯一正式输入

### 2.4 Renko / source time 扫描

至少扫描：

1. `renko_timeframes`
2. `generate_renko`
3. `calculate_renko`
4. 重复时间戳相关旧注释与旧测试口径

## 3. 需要重点回归的契约测试

### 3.1 pack producer

1. `py_entry/Test/backtest/test_data_pack_contract.py`
2. `py_entry/Test/backtest/test_result_pack_contract.py`
3. `py_entry/Test/backtest/test_extract_active_contract.py`
4. `py_entry/Test/backtest/test_strip_indicator_time_columns_contract.py`
5. `py_entry/Test/walk_forward/test_window_slice_contract.py`
6. `py_entry/Test/data_generator/test_data_ops_tools.py`

重点验证：

1. `build_data_pack(...)` 是唯一底层 `DataPack` producer 真值入口
2. `build_result_pack(...)` 是唯一底层 `ResultPack` producer 真值入口
3. `extract_active(...)` 是唯一正式 pair-transform producer
4. `build_full_data_pack(...)`、`build_time_mapping(...)`、`DataPackFetchPlanner.finish(...)`、`slice_data_pack(...)` 都最终委托给 `build_data_pack(...)`
5. `run_*` 结果构建与 `slice_result_pack(...)` 都最终委托给 `build_result_pack(...)`
6. Rust 生产代码中除 producer 真值入口内部外，不存在直接 `DataPack::new_checked(...)` / `ResultPack::new_checked(...)` 的 pack 产出路径

### 3.2 执行层行为等价

1. `py_entry/Test/execution_control/*`
2. `py_entry/Test/backtest/common_tests/*`
3. `py_entry/Test/indicators/*`
4. `py_entry/Test/performance/*`

重点验证：

1. `ExecutionStage` 只包含 `Indicator / Signals / Backtest / Performance`
2. `ArtifactRetention` 只包含 `AllCompletedStages / StopStageOnly`
3. `execution_stage / return_only_final` 到 `stop_stage / artifact_retention` 的迁移保持行为等价
4. 任意 `stop_stage × artifact_retention` 组合下，`mapping`、`ranges`、`base_data_key` 都保留在公开结果中
5. `SettingContainer { stop_stage: Indicator, artifact_retention: AllCompletedStages }` 与 `SettingContainer { stop_stage: Indicator, artifact_retention: StopStageOnly }` 都只返回 indicators
6. `SettingContainer { stop_stage: Signals, artifact_retention: AllCompletedStages }` 返回 indicators 与 signals；`SettingContainer { stop_stage: Signals, artifact_retention: StopStageOnly }` 只返回 signals
7. `SettingContainer { stop_stage: Backtest, artifact_retention: AllCompletedStages }` 返回 indicators、signals、backtest；`SettingContainer { stop_stage: Backtest, artifact_retention: StopStageOnly }` 只返回 backtest
8. `SettingContainer { stop_stage: Performance, artifact_retention: AllCompletedStages }` 返回全部阶段产物；`SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }` 只返回 performance

### 3.3 内部 pipeline

1. 与内部执行层相关的 Rust 测试
2. `py_entry/Test/backtest/common_tests/*`
3. `py_entry/Test/walk_forward/*`
4. 在 `src/backtest_engine/pipeline/` 模块新增轻量 contract test

重点验证：

1. `execute_single_pipeline(...)` 接受严格 `PipelineRequest`
2. `execute_single_pipeline(...)` 返回严格 `PipelineOutput`
3. `PipelineRequest` 采用完整枚举，即使部分变体当前没有真实调用
4. `PipelineRequest -> PipelineOutput` 的映射保持一一对应
5. `SignalsTo*` 只接受 raw indicators，不接受带 `time` 列的公开 indicators
6. `BacktestTo*` 只用于 `Performance`
7. `PipelineOutput` 不允许多返回阶段，也不允许少返回阶段
8. Rust 内部所有 single pipeline 语义调用点都收束到 `execute_single_pipeline(...)`
9. `build_result_pack(...)` 是唯一允许给 raw indicators 补 `time` 列的边界

### 3.4 WF / optimizer / sensitivity

1. `py_entry/Test/walk_forward/*`
2. `py_entry/Test/optimizer_benchmark/*`
3. `py_entry/Test/sensitivity/*`

重点验证：

1. `run_walk_forward(...)` 只接受 `SettingContainer { stop_stage: Performance, artifact_retention: AllCompletedStages }`
2. `run_optimization(...)` 只接受 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }`
3. `run_sensitivity_test(...)` 只接受 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }`
4. WF 不再依赖 precheck
5. WF replay 与 stitched performance 收口到新执行链
6. optimizer / sensitivity 不再各自保留旧 single 执行旁路
7. `evaluate_param_set(...)` 内部固定等价于 `ScratchToPerformanceStopStageOnly`
8. Python `Backtest.walk_forward()` / `Backtest.optimize()` / `Backtest.sensitivity()` / `Backtest.optimize_with_optuna()` 必须分别编译出各自 Rust mode guard 要求的正式 `SettingContainer`

### 3.5 export / display / bundle

1. `py_entry/Test/result_export/*`
2. 与 display / bundle 相关的 smoke 测试

重点验证：

1. single 路径是 `single result -> single adapter -> ExportPayload schema -> packager -> bundle -> display`
2. WF stitched 路径是 `WF result -> WF adapter -> ExportPayload schema -> packager -> bundle -> display`
3. single 与 WF stitched 仍能生成既有 Zip 结构
4. `param_set/param.json` 只由 single adapter 负责
5. `backtest_schedule/backtest_schedule.json` 只由 WF adapter 负责

### 3.6 Python runner view / bundle

1. `py_entry/Test/test_public_api_stub_contract.py`
2. `py_entry/Test/result_export/*`
3. `py_entry/Test/walk_forward/*`
4. 新增 `py_entry/Test/test_runner_view_contracts.py`
5. 与 `py_entry/runner` 公开对象相关的 smoke / 契约测试

重点验证：

1. `Backtest.run()` 返回 `SingleBacktestView`
2. `Backtest.batch()` 返回 `BatchBacktestView`
3. `Backtest.walk_forward()` 返回 `WalkForwardView`
4. `Backtest.optimize()` 返回 `OptimizationView`
5. `Backtest.sensitivity()` 返回 `SensitivityView`
6. `Backtest.optimize_with_optuna()` 返回 `OptunaOptimizationView`
7. 旧命名 `RunResult`、`BatchResult`、`WalkForwardResultWrapper`、`OptimizeResult`、`SensitivityResultWrapper`、`OptunaOptResult` 已退出正式公开面
8. `WalkForwardView` 不再暴露 `run_result` 代理
9. Python 结果层不再保存 `context: dict`
10. Python 结果层不再通过 `__getattr__` 透传原始对象
11. 所有正式 view 都统一具备 `build_report()` / `print_report()`
12. `SingleBacktestView.prepare_export(...)` 与 `WalkForwardView.prepare_export(...)` 是唯一正式导出入口
13. `PreparedExportBundle.display/save/upload` 是唯一正式消费入口
14. `BatchBacktestView`、`OptimizationView`、`SensitivityView`、`OptunaOptimizationView` 不定义 `prepare_export(...)`
15. `py_entry/runner/__init__.py` 与公开 stub 中不再重导出旧 wrapper 名
16. 若保留 `py_entry/runner/results/*` 文件，它们也不再承担正式公开 API 语义
17. 所有正式 `*View.session` 都是 `RunnerSession`，并承载 `data_pack / template_config / engine_settings / enable_timing`
18. 当前验证采用“轻量契约测试 + 既有行为回归”双层覆盖，而不是只靠 smoke test 推断公开 contract
19. `OptimizationView` / `SensitivityView` / `WalkForwardView` / `OptunaOptimizationView.session.engine_settings` 必须记录该 mode 实际执行使用的正式设置快照
20. 已返回 view 的 `session.engine_settings` 不得被后续 `Backtest.engine_settings` mutation 回写污染

### 3.7 source time / Renko

1. `py_entry/Test/data_generator/*`
2. `py_entry/Test/walk_forward/*`
3. 相关 Rust stitched 检查测试

重点验证：

1. source 缺少 `time` 列、`time` 不是 `Int64`、`time` 含空值时都必须 fail-fast
2. 重复时间戳 source 必须 fail-fast
3. stitched 后 base 与非 base source 都必须严格递增
4. stitched 失败信息至少包含 `source_key`
5. 对外不再保留 `renko_timeframes`、`generate_renko`、`calculate_renko` 正式入口
6. 测试注释、source key 示例与测试参数构造中，不保留 `renko_*` 或 `renko_timeframes` 正式口径

## 4. stub 与公共接口验证

这次任务必须显式确认：

1. `python/pyo3_quant/_pyo3_quant/__init__.pyi` 中 pack direct constructor 与 setter 已退出
2. `SettingContainer` 字段已迁移为 `stop_stage / artifact_retention`
3. backtest 公开入口命名已收口为 `run_single_backtest(...)` / `run_batch_backtest(...)`
4. `run_backtest_engine(...)` / `py_run_backtest_engine(...)` 已退出公开 stub 与正式文档
5. `PipelineRequest` / `PipelineOutput` 未进入公开 stub
6. `py_run_*` 只是 Rust wrapper 符号，不承担业务逻辑
7. Python runner 公开对象名已迁移到正式 `*View` 集合与 `PreparedExportBundle`

## 5. 最终通过标准

本任务完成前，至少应满足：

1. `Legacy Kill List` 关键字扫描通过
2. `just check` 通过
3. `just test` 通过
4. 关键回归测试覆盖本任务新增 breaking 面
5. `04_review` 已记录最终验收结果与残余风险
