# 执行记录

## 1. 本轮实际修复

1. Stage 1：收口 pack producer 真值入口，移除 Python stubs 中 `DataPack` / `ResultPack` 的公开构造与 setter，并让 `active_extract.rs`、`slicing.rs` 回到 producer 真值体系。
2. Stage 2：新增 `src/backtest_engine/pipeline/` 模块目录，把内部执行主链拆成 `types / settings / public_result / validation / executor / tests` 六层，实现 `PipelineRequest -> execute_single_pipeline(...) -> PipelineOutput`，并补上 `evaluate_param_set(...)` 与模式设置校验 helper。
3. Stage 2：将 backtest 正式入口从 `run_backtest_engine(...)` / `py_run_backtest_engine(...)` 收口到 `run_batch_backtest(...)` / `py_run_batch_backtest(...)`，同步完成 `top_level_api.rs` 与 module registry 重构。
4. Stage 2：删除 `BacktestContext` 与 `utils/context.rs`，把 WF / optimizer / sensitivity 的 single pipeline 语义统一拉回新执行主链。
5. Stage 3：删除 Python `validate_wf_indicator_readiness(...)` 正式入口，并移除 workflow 对它的显式依赖。
6. Stage 3：为 `run_walk_forward(...)`、`run_optimization(...)`、`run_sensitivity_test(...)` 增加正式模式设置硬约束。
7. Stage 3：将 Python runner 收口为 `Backtest + RunnerSession + *View + PreparedExportBundle` 四层，`Backtest.*` 正式返回类型改为 `SingleBacktestView / BatchBacktestView / WalkForwardView / OptimizationView / SensitivityView / OptunaOptimizationView`。
8. Stage 3：将 single / WF 导出入口改为 `prepare_export(...)`，display/save/upload 改为正式消费 `PreparedExportBundle`，并取消 `py_entry.io` 对旧 raw-object converter 的正式 re-export。
9. Stage 3：将 stitched source time 校验从“非递减”收口到“严格递增”，移除 `renko_timeframes`、`generate_renko`、`calculate_renko` 的正式导出与数据生成入口使用面，删除 `py_entry/data_generator/renko_generator.py` 历史残留源码，并清理 `brick_size` 配置字段与测试辅助中的 Renko 示例口径。
10. Stage 4：同步迁移相关测试、stubs 与结构文档，去除旧 precheck / Renko / 旧 runner 命名口径，并补做 `prepare_export(...)` 术语统一与 review 回填。
11. Stage 4：将 `test_runner_view_contracts.py` 中的 typed fake raw 收口为 `typing.cast(...)` 边界，修复 `just check` 对 `WalkForwardView / OptimizationView / SensitivityView` raw 类型的静态校验失败。
12. Stage 4：收紧 `WalkForwardView.stitched_equity` 的失败语义，仅在 stitched `backtest_result` 缺失时返回空数组；若 `equity` 列缺失则直接报错，不再 `except Exception: return []` 静默吞错。
13. Stage 4：补充公开面旧名字自动化护栏测试，并重新串行执行 `just check`、`just test`，以当前树真实结果完成 Close Gate 回填。
14. Stage 4：修复 Python runner mode setting 编译缺口，`Backtest.walk_forward()` 固定使用 WF 全产物设置，`Backtest.optimize()` / `Backtest.sensitivity()` 固定使用 performance-only 设置，避免 strategy_hub demo 的优化阶段把全产物设置误传给 Rust optimizer。
15. Stage 4：将 `py_entry/strategy_hub/demo.ipynb` 的 code cells 收口到最终态示例命名，区分 `*View` 与 `PreparedExportBundle`，不再把 view 变量原地重绑定成 bundle。
16. Stage 4：补齐 `Backtest.optimize_with_optuna()` 的 performance-only mode setting contract，Optuna batch / parallel trial 不再经由 `Backtest.run()` / `Backtest.batch()` 透传实例设置。
17. Stage 4：将 `RunnerSession.engine_settings` 收口为执行时快照，避免 view 与导出解释层被后续 `Backtest.engine_settings` mutation 回写污染。

## 2. 本轮未处理范围

1. `py_entry/strategy_hub/demo.ipynb` 当前仍带有用户侧未暂存改动；本轮只清理 code cells 的正式 API 与变量语义，不处理历史输出与 notebook metadata。
