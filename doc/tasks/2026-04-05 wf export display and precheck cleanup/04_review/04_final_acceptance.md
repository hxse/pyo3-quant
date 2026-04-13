# 最终验收

## 1. 验证结果

1. `just check` 通过。
2. `just test` 通过，结果为 `597 passed, 45 skipped`。
3. 阶段验收结果已回填到 `02_stage_acceptance.md`。
4. AI pre-review / post-review 与 `Legacy Kill List` 最终扫描结果已回填到 `03_fix_log.md`。
5. 本轮最终串行验收时间点为 `2026-04-12 23:21:00 CST`。

## 2. 本轮收口结论

1. Python precheck 已退出正式 gate；pack 合法性真值已收口到 producer，执行 fail-fast 真值已收口到 Rust 正式执行主链。
2. WF / optimizer / sensitivity 的模式设置不再静默放行非法组合。
3. stitched source time 与 Renko 正式口径已按本 task 的 contract 收紧；Renko 配置面、源码入口、测试构造与测试辅助示例口径均已清理。
4. 结构文档与 task spec 已同步到新的 `run_batch_backtest`、`*View`、`prepare_export(...) -> PreparedExportBundle` 口径；`02_spec` 中 pipeline contract 已拆成 request/output 与 mode/failure 两份正式真值文件。
5. `py_entry.io` 不再把旧 raw-object converter 作为正式公开接口 re-export，Renko 历史源码残留已清理。
6. A 类任务要求的阶段验收、最终扫描与 review 证据链已补齐，不再只靠 `01_execution_log.md` 与 `04_final_acceptance.md` 两份材料闭环。
7. `test_runner_view_contracts.py` 的静态类型边界已与正式 raw 注解对齐，`WalkForwardView.stitched_equity` 的 quietly wrong 吞错路径已删除，Close Gate 所需的 `just check` / `just test` 已在当前树真实闭环。
8. Python `Backtest` 门面已显式编译各模式所需的正式 `SettingContainer`，strategy_hub demo 的 `optimize()` / `sensitivity()` / `walk_forward()` / `optimize_with_optuna()` 路径不再依赖调用方手动切换 `engine_settings`。
9. `RunnerSession.engine_settings` 已改为执行时快照，已返回 view 与后续导出解释层不会被 `Backtest.engine_settings` 后续 mutation 污染。
10. 失效 notebook 迁移脚本已删除，结构文档的核心枚举总览已补齐 `ArtifactRetention`。
11. `src/backtest_engine/pipeline/` 已按 request/output、settings、validation、executor、public_result、tests 分层拆开，不再由单个 `pipeline.rs` 承担多重职责。

## 3. 残余风险

1. `py_entry/strategy_hub/demo.ipynb` 已清理 code cells 的正式 API 与变量语义，但该文件当前仍带有用户侧未暂存改动；历史输出与 notebook metadata 未纳入本轮清理。
