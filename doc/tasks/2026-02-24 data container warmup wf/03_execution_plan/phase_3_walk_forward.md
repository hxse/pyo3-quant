# Phase 3 执行文档：Walk-Forward 全链路落地与总收口

## 1. 目标

完成 WF 重构（无 `transition_bars`）、注入链路、窗口与拼接产物，并完成全项目最终验收。

## 2. 本阶段范围

1. `WalkForwardConfig` 收敛：
   - 删除 `transition_bars`
   - 保留 `train_bars/test_bars/inherit_prior/optimizer_config`
   - 新增 `test_warmup_source`
2. 落地窗口算法：
   - 第 0 窗模板 + `step=test_bars` 平移
   - `BorrowFromTrain` / `ExtendTest` 双模式
3. 落地测试执行链：
   - `run_single_backtest(ExecutionStage::Signals)`
   - 注入
   - `backtester::run_backtest`
   - `performance_analyzer::analyze_performance`
4. 产物口径：
   - `window_results` 只保留每窗非预热测试段
   - `stitched_result` 只保留拼接后的非预热测试段
5. `WindowArtifact` 字段收敛到新结构（删除旧字段）。
6. stitched 资金列重建与二次一致性校验（time 列一致）。
7. PyO3 + pytest + 端到端回归收口。

## 3. 非目标（明确不做）

1. 不再回头改 Phase 1/2 的口径定义。
2. 不保留旧 WF 兼容层。

## 4. 实施步骤

1. E1：先改窗口索引与运行区间构建。
2. E2：再改注入与测试执行链。
3. E3：最后改产物字段、拼接与一致性校验。
4. 同步完成 WF 相关 pytest 迁移。

## 5. 验收命令

1. `just check`
2. `just test-py path="py_entry/Test/backtest/test_walk_forward_guards.py"`
3. `just test-py path="py_entry/Test/backtest/test_walk_forward_new_pipeline.py"`
4. `just test`

## 6. 完成标准

1. WF 新链路与文档完全一致。
2. `window_results` / `stitched_result` 产物结构稳定。
3. 全项目 `check/test` 全绿。

## 7. 风险与应对

1. 风险：窗口公式或注入点偏移导致结果漂移。
   应对：用文档数值样例做固定回归断言。
2. 风险：字段删除导致 Python 侧读取失败。
   应对：在本阶段统一改 PyO3/.pyi/pytest，禁止跨阶段残留。
