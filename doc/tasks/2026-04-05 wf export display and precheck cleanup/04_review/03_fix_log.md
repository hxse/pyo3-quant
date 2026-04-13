# 修复与最终扫描记录

## 1. AI pre-review 结果沉淀

本轮执行前的 AI pre-review 以 `03_execution/*` 为准，重点确认了下面三类 Gate：

1. Stage 1 必须先收口 pack producer，再进入执行主链重构。
2. Stage 2 必须把 `BacktestContext`、旧字段与旧 batch 入口一起收口，避免只改 stub 不改运行时。
3. Stage 3 必须同时覆盖 Python runner view、export bundle、WF stitched 与 source time，不能只做单点修补。

## 2. AI post-review 结果沉淀

本轮 post-review 重点复核了下面几条：

1. `PipelineRequest` / `PipelineOutput` 是否真的进入正式执行主链，而不是只停留在 stub / 文档层。
2. `run_batch_backtest(...)`、`py_run_batch_backtest(...)` 是否真正替换旧 batch 命名。
3. `RunnerSession + *View + PreparedExportBundle` 是否已经成为 Python runner 正式分层。
4. `py_entry.io` 是否仍保留旧 raw-object converter 的正式公开面。
5. Renko 残留与 `format_for_export` 旧术语是否仍在正式代码路径中出现。

## 3. Legacy Kill List 最终扫描

### 3.1 本轮最终扫描范围

1. 正式源码与生成接口面：`src/`、`python/`、`py_entry/`
2. 结构文档：`doc/structure/`
3. 公开面护栏测试：`py_entry/Test/test_public_surface_legacy_name_guard.py`

扫描解释：

1. `py_entry/Test/test_public_surface_legacy_name_guard.py` 是旧公开名字的自动化黑名单载体，文件内部保留旧关键词是测试实现需要，不计入“旧入口回流”。
2. `doc/tasks/` 是任务快照与历史证据链，不作为 Legacy Kill List 清零扫描对象。
3. 正式源码扫描排除护栏测试自身后执行，避免用护栏测试里的旧词污染清零结论。

### 3.2 已确认清零的关键词

1. 正式源码与生成接口面已清零：`execution_stage`
2. 正式源码与生成接口面已清零：`return_only_final`
3. 正式源码与生成接口面已清零：`BacktestContext`
4. 正式源码与生成接口面已清零：`run_backtest_engine`
5. 正式源码与生成接口面已清零：`py_run_backtest_engine`
6. 正式源码与生成接口面已清零：`validate_wf_indicator_readiness`
7. 正式源码与生成接口面已清零：`format_for_export`
8. 正式源码与生成接口面已清零：`renko_timeframes`
9. 正式源码与生成接口面已清零：`generate_renko`
10. 正式源码与生成接口面已清零：`calculate_renko`
11. 正式源码与生成接口面已清零：`brick_size`
12. 正式源码与生成接口面已清零：`renko_`
13. 正式源码与生成接口面已清零：`run_result`
14. 正式源码与生成接口面已清零：`context={`
15. 正式源码与生成接口面已清零：`export_buffers`
16. 正式源码与生成接口面已清零：`export_zip_buffer`

### 3.3 保留说明

1. `DataPack::new_checked` / `ResultPack::new_checked` 已从 producer 真值入口之外的生产路径清理掉；当前只允许 `build_data_pack(...)`、`build_result_pack(...)` 这类 producer 真值入口在内部直接调用它们。
2. `__getattr__` 关键词当前只命中 `py_entry/trading_bot/live_strategy_callbacks.py`；该处属于 live bot callback 委托桥接，不属于 runner view / raw-object proxy 残留，因此按非目标保留处理。
3. `py_entry/strategy_hub/demo.ipynb` 存在用户侧未暂存改动；本轮只清理 code cells 的正式 API 与变量语义，不处理历史输出与 notebook metadata。

## 4. 本轮补修记录

1. 补齐 A 类任务所需的阶段验收与最终扫描沉淀，闭合 `04_review` 证据链。
2. 扩写 `01_execution_log.md`，把 Stage 2 / Stage 3 的核心落地点明确回填。
3. 从 `py_entry.runner.results.__all__` 中移除 `OptunaOptimizationRaw`，避免扩大正式结果层命名面。
4. 将 `test_runner_view_contracts.py` 中的 fake raw 显式收口到 `typing.cast(...)` 边界，修复 `just check` 的 `invalid-argument-type` 报错。
5. 为 `WalkForwardView.stitched_equity` 增加缺少 `equity` 列时的 fail-fast 约束，并补充对应契约测试。
6. 新增 `test_public_surface_legacy_name_guard.py`，只扫描正式公开面，防止旧名字与旧入口重新回流。
7. 修复 Python runner mode setting 编译缺口：`Backtest.walk_forward()` 固定编译为 `Performance + AllCompletedStages`，`Backtest.optimize()` / `Backtest.sensitivity()` 固定编译为 `Performance + StopStageOnly`。
8. 同步更新 runner 契约测试、optimizer / sensitivity / WF 模式测试，以及 `strategy_hub/demo.ipynb` code cells，避免示例和测试继续依赖错误的设置透传行为。
9. 补齐 `Backtest.optimize_with_optuna()` 的 mode setting 编译：Optuna batch / parallel trial 固定使用 `Performance + StopStageOnly`，`OptunaOptimizationView.session.engine_settings` 记录该执行设置。
10. 修复 `RunnerSession.engine_settings` 活引用问题，view 持有执行时快照，不再被后续 `Backtest.engine_settings` mutation 回写污染。
11. 删除 `OtherParams.brick_size` 配置面残留，并清理 data generator / signal 测试辅助里的 Renko 示例与注释口径。
12. 删除失效的 `py_entry/debug/fix_notebooks.py` 旧 API 迁移脚本，避免 notebook 被改写到 `BacktestRunner` / `.setup(...)` / `.format_results_for_export(...)` 等不存在的旧入口。
13. 清理 `py_entry/runner/params.py` 中旧方法名注释，并补齐 `doc/structure/pyo3_interface_design.md` 的 `ArtifactRetention` 枚举总览。
14. 修正 `doc/signal.md` 的 source time 约束文案，使其与 `src/backtest_engine/data_ops/source_contract.rs` 和本 task spec 的 producer 真值口径一致。
15. 将 `02_spec/03_pipeline_and_mode_contracts.md` 拆分为 `03_pipeline_request_and_output_contracts.md` 与 `04_pipeline_mode_and_failure_contracts.md`，并顺延 export / view / source-time spec 文件名，确保单文件长度与最终态写法符合 task 规范。
16. 将 `src/backtest_engine/pipeline.rs` 拆分为 `src/backtest_engine/pipeline/` 目录模块，把 request/output、setting compile、validation、executor、public result、tests 分层落地。
17. 将正式源码中的泛化 `run_result` 局部变量收口为 `result_view` 命名，避免 Legacy Kill List 扫描把普通 view 变量误判为旧 runner proxy。

## 5. 本轮最终验证

1. 本轮于 `2026-04-12 23:21:00 CST` 完成 `just check -> just test` 的串行 gate 验收。
2. `just check` 在当前未暂存树通过；`just test` 在当前未暂存树通过，结果为 `597 passed, 45 skipped`。
