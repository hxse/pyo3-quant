# Breaking 与迁移清单

## 1. 行为等价边界

本任务不是“全量逻辑完全等价”的纯结构重构。

正式边界固定为：

1. `03-10` 已冻结的 warmup / window / stitched 主算法不改，相关执行行为必须保持等价。
2. `execution_stage / return_only_final` 到 `stop_stage / artifact_retention` 的迁移必须保持组合语义等价。
3. single / batch 的公开结果矩阵，以及 WF / optimizer / sensitivity 的既有模式语义必须保持等价。
4. Python precheck 删除、pack producer 收口、source time 严格递增 contract、Renko 正式入口退出，这些属于有意的 breaking 收紧，不按“等价迁移”解释。

## 2. `SettingContainer` 公开字段变更

1. `execution_stage` 更名为 `stop_stage`。
2. `return_only_final` 替换为 `artifact_retention`。
3. `false` 的旧行为映射为 `ArtifactRetention::AllCompletedStages`。
4. `true` 的旧行为映射为 `ArtifactRetention::StopStageOnly`。

## 3. `ExecutionStage` 枚举收口

1. `ExecutionStage::Idle` 退出正式枚举集合。
2. 正式公开阶段只保留 `Indicator / Signals / Backtest / Performance`。

## 4. 公开 backtest 入口命名收口

1. 保留 `run_single_backtest(...)` 作为 single 模式正式入口。
2. `run_backtest_engine(...)` 退出正式命名，改为 `run_batch_backtest(...)`。
3. `py_run_backtest_engine(...)` 同步退为 `py_run_batch_backtest(...)`。

## 5. 执行层内部模型收口

1. 内部单次执行器收口为 `execute_single_pipeline(...)`。
2. `PipelineStart` 退出正式设计。
3. 内部请求收口为严格 `PipelineRequest`。
4. 内部输出收口为严格 `PipelineOutput`。
5. `PipelineArtifacts` 退出正式设计。
6. 参数样本评估收口为 `evaluate_param_set(...)`。

## 6. `BacktestContext` 退出正式设计

1. `BacktestContext` 代码对象被删除。
2. `utils/context.rs` 退出执行主链。
3. WF replay 不再经由行为式 context 承接控制流。

## 7. `ResultPack` 边界收口

1. `ResultPack` 回到公开边界对象的位置。
2. 内部单次执行器与样本评估逻辑不再把 `ResultPack` 当内部中间货币。
3. raw indicators 只在 `build_result_pack(...)` 边界补 `time` 列。
4. 底层 `build_result_pack(...)` 继续使用 `data + indicators/signals/backtest/performance` 五参数输入；`data + PipelineOutput` 这一层正式收口为 `build_public_result_pack(...)`。
5. WF 主链不再手动拆 `ResultPack` 再调用局部 leaf 阶段函数。

## 8. 模式级 `SettingContainer` 约束冻结

1. `run_walk_forward(...)` 的合法设置为 `SettingContainer { stop_stage: Performance, artifact_retention: AllCompletedStages }`。
2. `run_optimization(...)` 的合法设置为 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }`。
3. `run_sensitivity_test(...)` 的合法设置为 `SettingContainer { stop_stage: Performance, artifact_retention: StopStageOnly }`。

## 9. PyO3 暴露边界收口

1. 本次没有新增独立的模式入口对象；新增对外可见的只有 `SettingContainer.artifact_retention` 及其枚举类型 `ArtifactRetention`。
2. `SettingContainer` 保留公开对象地位，但字段改为 `stop_stage / artifact_retention`。
3. `PipelineRequest` 与 `PipelineOutput` 不进入 PyO3 暴露面。
4. `py_run_*` 仅保留为 Rust wrapper 符号。
5. `run_*` 仍是正式模式业务入口命名。
6. `DataPack` 与 `ResultPack` 继续作为公开类型存在，但不再公开 `__new__` 与 setter。

## 10. 内部调用面收口

1. Rust 内部 single pipeline 语义统一收口到 `execute_single_pipeline(...)`。
2. 当前 `top_level_api.rs`、`walk_forward/window_runner.rs`、`optimizer/runner/mod.rs`、`optimizer/evaluation.rs`、`sensitivity/runner.rs` 中的 single 执行路径都必须完成迁移。
3. `walk_forward/window_runner.rs` 与 `walk_forward/stitch.rs` 中直接 `analyze_performance(...)` 的阶段控制路径也必须收口到新的执行设计。
4. 本任务不定义也不实现 `FromIndicators` 起点。
5. 内部请求必须编译为严格 `PipelineRequest`，不得再以“起点 + stop_stage + retention + \`Option carried_*\`”临时拼装。
6. 内部执行结果必须返回严格 `PipelineOutput`，不得再返回通用 `Option` 结果袋。
7. `active_extract.rs` 与 `slicing.rs` 中直接 `new_checked(...)` 的 pack 产出路径必须收口到 producer 真值入口体系。

## 11. pack producer / precheck 收口

1. Python `validate_wf_indicator_readiness(...)` 退出正式入口体系。
2. `DataPack` 与 `ResultPack` 收口为 formal contract object。
3. producer 真值入口固定收口为 `build_data_pack(...)`、`build_result_pack(...)`、`extract_active(...)`。
4. `build_full_data_pack(...)`、`build_time_mapping(...)`、`DataPackFetchPlanner.finish(...)`、`slice_data_pack(...)` 最终都委托给 `build_data_pack(...)`。
5. `run_*` 结果构建与 `slice_result_pack(...)` 最终都委托给 `build_result_pack(...)`。
6. 本任务不引入共享入口 guard，也不引入 `skip_validation`。

## 12. source time / Renko 收口

1. source time contract 统一收口为“存在 `time` 列、`Int64`、不为空、严格递增”。
2. 重复时间戳 source 不再被任何正式入口接受。
3. `renko_timeframes` 退出正式配置面。
4. `generate_renko / calculate_renko` 退出正式对外导出。
5. Renko 相关运行时、配置、测试、注释、示例与文档残留都属于本次正式清扫范围。

## 13. export adapter / packager 收口

1. packager 只消费符合 `ExportPayload` schema 的标准化导出负载。
2. `RunResult` 不再承担 WF stitched 导出兼容状态。
3. `backtest_schedule/backtest_schedule.json` 只由 WF adapter 负责。
4. `param_set/param.json` 只由 single adapter 负责。

## 14. Python runner wrapper 收口

1. Python runner 结果层正式收口为 `SingleBacktestView`、`BatchBacktestView`、`WalkForwardView`、`OptimizationView`、`SensitivityView`、`OptunaOptimizationView`。
2. `RunResult`、`BatchResult`、`WalkForwardResultWrapper`、`OptimizeResult`、`SensitivityResultWrapper`、`OptunaOptResult` 退出正式命名。
3. `RunnerSession` 取代 Python 结果层里的 `context: dict`。
4. `format_for_export(...)` 退出正式命名，改为 `prepare_export(...)`。
5. `PreparedExportBundle` 成为 display/save/upload 的唯一正式输入对象。
6. `WalkForwardView` 不再惰性拼 single 结果代理。
7. `__getattr__` 透传式 wrapper 不再保留在正式结果层。
8. `Backtest.run / batch / walk_forward / optimize / sensitivity / optimize_with_optuna` 的正式返回类型全部迁移到 `*View`。
9. 只有 `SingleBacktestView` 与 `WalkForwardView` 定义 `prepare_export(...)`；其他 view 不新增空导出入口。
10. 旧 `results/*` 文件若仍存在，只能作为内部实现细节，不得继续承担正式公开命名或公开 re-export。

## 15. 旧字段使用面迁移覆盖

为保证 `execution_stage / return_only_final` 的行为等价迁移无遗漏，本 task 必须覆盖：

1. Rust 类型与 stub：
   `src/types/inputs/settings.rs`、`python/pyo3_quant/_pyo3_quant/__init__.pyi`
2. Python 默认配置与 runner 构造：
   `py_entry/runner/setup_utils.py`、`py_entry/strategy_hub/core/config.py`、`py_entry/Test/shared/backtest_builders.py`
3. Python 运行与调试入口：
   `py_entry/runner/backtest.py`、`py_entry/scanner/strategies/_scan_backtest.py`、`py_entry/debug/*`
4. WF 内部覆盖写法：
   `src/backtest_engine/walk_forward/runner.rs`、`src/backtest_engine/walk_forward/window_runner.rs`
5. 序列化与导出：
   `py_entry/io/_converters_bundle.py`
6. 主要测试与 benchmark：
   `py_entry/Test/execution_control/*`
   `py_entry/Test/backtest/common_tests/*`
   `py_entry/Test/walk_forward/*`
   `py_entry/Test/result_export/*`
   `py_entry/Test/indicators/*`
   `py_entry/Test/performance/*`
   `py_entry/Test/optimizer_benchmark/*`
   `py_entry/Test/sensitivity/*`
   `py_entry/benchmark/*`

## 16. pack 直接构造使用面迁移覆盖

为保证“pack object 只能由 producer 真值入口产出”的规则真正落地，本 task 必须覆盖：

1. Python 公开 stub 与类型导出：
   `python/pyo3_quant/_pyo3_quant/__init__.pyi`、`py_entry/types/__init__.py`
2. 公开接口文档：
   `doc/structure/pyo3_interface_design.md`
3. Python 运行时复制 / 包装辅助：
   `py_entry/runner/results/run_result.py`
4. Python 测试辅助与契约测试：
   `py_entry/Test/signal/utils/mapping_helpers.py`
   `py_entry/Test/backtest/common_tests/test_top_level_api_validation.py`
   `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`
   `py_entry/Test/backtest/test_extract_active_contract.py`
5. Rust 生产代码中的旁路构造：
   `src/backtest_engine/data_ops/active_extract.rs`
   `src/backtest_engine/data_ops/slicing.rs`

## 17. Python wrapper 迁移覆盖

为保证 Python runner wrapper 收口不只停在 adapter 层，本 task 必须覆盖：

1. Python 公开门面与导出：
   `py_entry/runner/__init__.py`
   `py_entry/runner/backtest.py`
   `py_entry/runner/display/*`
2. Python 结果层：
   `py_entry/runner/results/__init__.py`
   `py_entry/runner/results/run_result.py`
   `py_entry/runner/results/batch_result.py`
   `py_entry/runner/results/wf_result.py`
   `py_entry/runner/results/opt_result.py`
   `py_entry/runner/results/sens_result.py`
   `py_entry/runner/results/optuna_result.py`
3. Python 导出与 bundle：
   `py_entry/io/_converters_bundle.py`
   `py_entry/io/result_export.py`
4. 主要测试与公开契约：
   `py_entry/Test/test_public_api_stub_contract.py`
   `py_entry/Test/result_export/*`
   `py_entry/Test/walk_forward/*`
5. 公开迁移闭环：
   `Backtest.* -> *View`
   `prepare_export(...) -> PreparedExportBundle`
   旧 wrapper 名从 `py_entry/runner/__init__.py`、stub 与公开示例中清零
