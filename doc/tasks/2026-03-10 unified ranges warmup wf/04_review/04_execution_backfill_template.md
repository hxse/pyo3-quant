# 统一 Ranges / Warmup / WF 回补模板

对应文档：

1. [01_execution_plan.md](../03_execution/01_execution_plan.md)
2. [03_execution_stages_and_acceptance.md](../03_execution/03_execution_stages_and_acceptance.md)
3. [02_test_plan.md](../03_execution/02_test_plan.md)
4. [05_pre_execution_ai_review.md](../03_execution/05_pre_execution_ai_review.md)
5. [01_post_execution_review.md](./01_post_execution_review.md)

本页只记录代码落地、验收命令、验收结果与剩余风险，不记录审阅通过状态。
执行前 AI 审阅结论统一记录在 [05_pre_execution_ai_review.md](../03_execution/05_pre_execution_ai_review.md)。
执行后补充审阅结论统一记录在 [01_post_execution_review.md](./01_post_execution_review.md)。

统一模板：

1. 状态：`未开始 / 进行中 / 已完成`
2. 实际修改文件：
3. 实际验收命令：
4. 验收结果：
5. 若未跑测试：
   - 必须明确阻塞原因
   - 不允许用审阅结论替代阶段验收
6. 剩余风险 / 待后续：

说明：

1. 若 `03_execution` 中的历史 gate、建议新增测试文件或原计划路径，与当前仓库实际文件名不一致，统一在本页记录现行可回放入口。
2. `03_execution` 保留 planning 阶段冻结内容；路径漂移、替代 gate 与覆盖吸收，统一以后验回填形式记录在本页。

## 1. 阶段 A1

1. 状态：`已完成`
2. 实际修改文件：
   - `src/types/inputs/data.rs`
   - `src/backtest_engine/data_ops/time_projection.rs`
   - `src/backtest_engine/data_ops/data_pack_builder.rs`
   - `src/backtest_engine/data_ops/warmup_requirements.rs`
   - `src/backtest_engine/data_ops/mod.rs`
3. 实际验收命令：
   - 历史阶段已完成；当前仓库中执行文档原列出的 `py_entry/Test/backtest/test_data_pack_contract.py` 与 `py_entry/Test/backtest/test_mapping_projection_contract.py` 已不存在，无法按旧路径回放
   - 当前分支已补跑：`just check`
   - 当前分支已补跑：`just test`
4. 验收结果：
   - 当前分支 `just check` 与 `just test` 均通过
   - A1 原专属 Python gate 文件已被后续测试重组吸收，执行文档存在路径漂移
5. 若未跑测试：
   - 未逐条回放 A1 原专属 Python gate
   - 原因：当前仓库已不存在对应测试文件，不能伪造历史路径
6. 剩余风险 / 待后续：
   - 建议后续若再做大重构，补一套新的 A1 dedicated builder contract gate，避免再次依赖历史文件名

## 2. 阶段 A2

1. 状态：`已完成`
2. 实际修改文件：
   - `src/types/outputs/backtest.rs`
   - `src/backtest_engine/data_ops/result_pack_builder.rs`
   - `src/backtest_engine/data_ops/active_extract.rs`
   - `src/backtest_engine/performance_analyzer/mod.rs`
3. 实际验收命令：
   - 历史阶段已完成；当前仓库中执行文档原列出的 `test_result_pack_contract.py / test_strip_indicator_time_columns_contract.py / test_performance_contract.py / test_extract_active_contract.py` 已不存在，无法按旧路径回放
   - 当前分支已补跑：`just check`
   - 当前分支已补跑：`just test`
4. 验收结果：
   - 当前分支 `just check` 与 `just test` 均通过
   - A2 原专属 Python gate 文件已被后续测试重组吸收，执行文档存在路径漂移
5. 若未跑测试：
   - 未逐条回放 A2 原专属 Python gate
   - 原因：当前仓库已不存在对应测试文件，不能伪造历史路径
6. 剩余风险 / 待后续：
   - 若后续继续拆分 backtest / result builder，可考虑恢复 dedicated contract tests，避免只靠全量回归兜底

## 3. 阶段 B

1. 状态：`已完成`
2. 实际修改文件：
   - `src/backtest_engine/data_ops/fetch_planner/*`
   - `src/types/inputs/mod.rs`
   - `py_entry/Test/data_generator/test_data_fetch_planner_contract.py`
3. 实际验收命令：
   - `just check`
   - `just test-py path="py_entry/Test/data_generator/test_data_fetch_planner_contract.py"`
4. 验收结果：
   - 通过
5. 若未跑测试：
   - 无
6. 剩余风险 / 待后续：
   - `03_execution_stages_and_acceptance.md` 原路径写成 `py_entry/Test/backtest/test_data_fetch_planner_contract.py`，本次已修正文档

## 4. 阶段 C

1. 状态：`已完成`
2. 实际修改文件：
   - `src/backtest_engine/top_level_api.rs`
   - `src/backtest_engine/backtester/mod.rs`
   - `src/backtest_engine/backtester/main_loop.rs`
   - `src/backtest_engine/backtester/data_preparer.rs`
   - `src/backtest_engine/backtester/signal_preprocessor.rs`
   - `src/backtest_engine/performance_analyzer/mod.rs`
   - `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`
3. 实际验收命令：
   - `just check`
   - `just test-py path="py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py"`
4. 验收结果：
   - 通过
5. 若未跑测试：
   - 无
6. 剩余风险 / 待后续：
   - 无新增；当前主链已稳定走 `DataPack / ResultPack`

## 5. 阶段 D1

1. 状态：`已完成`
2. 实际修改文件：
   - `src/backtest_engine/walk_forward/data_splitter.rs`
   - `src/backtest_engine/walk_forward/time_ranges.rs`
   - `src/backtest_engine/walk_forward/next_window_hint.rs`
   - `py_entry/Test/walk_forward/test_window_slice_contract.py`
3. 实际验收命令：
   - `just check`
   - `just test-rust-exact backtest_engine::walk_forward::data_splitter::tests::test_build_window_indices_contract`
   - `just test-rust-exact backtest_engine::walk_forward::next_window_hint::tests::test_next_window_hint_contract`
   - `just test-rust-exact backtest_engine::walk_forward::time_ranges::tests::test_build_window_time_ranges_contract`
   - `just test-py path="py_entry/Test/walk_forward/test_window_slice_contract.py"`
4. 验收结果：
   - 通过
5. 若未跑测试：
   - 无
6. 剩余风险 / 待后续：
   - 无；`WindowMeta` 与时间范围 helper 已切到正式主链

## 6. 阶段 D2

1. 状态：`已完成`
2. 实际修改文件：
   - `src/backtest_engine/walk_forward/injection.rs`
   - `src/backtest_engine/walk_forward/window_runner.rs`
   - `src/backtest_engine/walk_forward/stitch.rs`
   - `src/backtest_engine/data_ops/warmup_requirements.rs`
   - `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
   - `py_entry/Test/walk_forward/test_wf_ignore_indicator_warmup_contract.py`
3. 实际验收命令：
   - `just check`
   - `just test-rust-exact backtest_engine::walk_forward::stitch::tests::test_stitched_replay_input_contract`
   - `just test-rust-exact backtest_engine::walk_forward::injection::tests::test_wf_signal_injection_contract`
   - `just test-rust-exact backtest_engine::data_ops::warmup_requirements::tests::test_ignore_indicator_warmup_contract`
   - `just test-py path="py_entry/Test/walk_forward/test_wf_signal_injection_contract.py"`
   - `just test-py path="py_entry/Test/walk_forward/test_wf_ignore_indicator_warmup_contract.py"`
4. 验收结果：
   - 通过
5. 若未跑测试：
   - 无
6. 剩余风险 / 待后续：
   - 无；跨窗注入、stitched 输入与 `ignore_indicator_warmup` dedicated contract 已冻结

## 7. 阶段 E

1. 状态：`已完成`
2. 实际修改文件：
   - `src/backtest_engine/backtester/params_selector.rs`
   - `src/backtest_engine/backtester/schedule_contract.rs`
   - `src/backtest_engine/backtester/schedule_policy.rs`
   - `src/backtest_engine/backtester/output_schema.rs`
   - `src/backtest_engine/backtester/state/output_buffers_iter/*`
   - `src/backtest_engine/backtester/output/output_init.rs`
   - `src/types/outputs/walk_forward.rs`
   - `src/types/inputs/walk_forward.rs`
   - `src/backtest_engine/walk_forward/runner.rs`
   - `src/backtest_engine/walk_forward/window_runner.rs`
   - `src/backtest_engine/walk_forward/stitch.rs`
   - `src/backtest_engine/walk_forward/next_window_hint.rs`
   - `src/backtest_engine/walk_forward/time_ranges.rs`
   - `py_entry/runner/results/wf_result.py`
   - `py_entry/strategy_hub/core/searcher_serialize.py`
   - `py_entry/runner/backtest.py`
   - `py_entry/Test/test_public_api_stub_contract.py`
   - `py_entry/Test/walk_forward/test_walk_forward_guards.py`
3. 实际验收命令：
   - `just check`
   - `just test-rust-exact backtest_engine::backtester::params_selector::tests::test_params_selector_contract`
   - `just test-rust-exact backtest_engine::backtester::schedule_contract::tests::test_validate_schedule_contiguity_contract`
   - `just test-rust-exact backtest_engine::backtester::schedule_policy::tests::test_validate_backtest_param_schedule_policy_contract`
   - `just test-rust-exact backtest_engine::backtester::output_schema::tests::test_build_schedule_output_schema_contract`
   - `just test-py path="py_entry/Test/test_public_api_stub_contract.py"`
   - `just test-py path="py_entry/Test/walk_forward/test_walk_forward_guards.py"`
4. 验收结果：
   - 通过
   - `WindowMeta / StitchedMeta / NextWindowHint` 已切到摘要最终公开边界
   - `WalkForwardConfig` 已切到 `train_active_bars / test_active_bars / min_warmup_bars / warmup_mode`
   - `WalkForwardConfig.inherit_prior` 与 `WfWarmupMode::NoWarmup` 已删除，不再保留过程兼容口径
   - 窗口规划主链已删除 `transition_range / transition_bars` 口径
5. 若未跑测试：
   - 执行文档原列出的 `test_stitched_contract.py` 当前仓库不存在
   - 该覆盖已由 `test_walk_forward_guards.py` 吸收，且最终总验收已覆盖 stitched 主链
6. 剩余风险 / 待后续：
   - 无新增；阶段 E 已完成最终公共切换与破坏性清理

## 8. 最终总验收记录

1. 实际修改文件汇总：
   - `src/types/inputs/*`
   - `src/types/outputs/*`
   - `src/backtest_engine/data_ops/*`
   - `src/backtest_engine/backtester/*`
   - `src/backtest_engine/walk_forward/*`
   - `src/backtest_engine/utils/context.rs`
   - `py_entry/runner/backtest.py`
   - `py_entry/runner/results/wf_result.py`
   - `py_entry/strategy_hub/core/searcher_serialize.py`
   - `py_entry/Test/data_generator/test_data_fetch_planner_contract.py`
   - `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`
   - `py_entry/Test/walk_forward/*`
   - `py_entry/Test/test_public_api_stub_contract.py`
2. 最终验收命令：
   - `just check`
   - `just test`
3. 最终验收结果：
   - 通过
   - 当前结果：`548 passed, 46 skipped`
4. 遗留问题：
   - 执行文档中原有部分阶段 gate 路径与当前仓库实际文件名存在漂移，本次已在回填中如实记录，并修正了 B / E 的明显错误入口
