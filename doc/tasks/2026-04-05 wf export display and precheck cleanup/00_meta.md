# 任务元信息

## 1. 任务描述

`2026-04-05 wf export display and precheck cleanup` 是 `2026-03-10 unified ranges warmup wf` 之后的后收口任务。它不重写已经冻结的 warmup / window / stitched 主算法，只负责清理仍在导出链路、Python precheck、执行入口边界、WF 局部 replay 架构和重复时间戳口径上制造双轨语义的残余，把这些外围解释层重新收口到 Rust 正式主流程。

这不是“全量逻辑等价”的纯结构整理任务。更准确地说：

1. 对 `03-10` 已冻结的主算法、single / batch 的公开 `stop_stage × artifact_retention` 语义，以及 WF / optimizer / sensitivity 的既有模式语义，这次任务要求行为等价。
2. 对 Python precheck、pack 自由构造、source time 严格递增 contract、Renko 正式入口与旧字段命名，这次任务包含有意的 breaking 收紧，不属于纯等价重构。

## 2. 任务级别

本任务定为 `A 类任务`。

原因：

1. 它横跨 Rust 顶层入口、WF 局部 replay、Python workflow、导出链路、测试和结构文档，不是单点修补。
2. 它牵涉执行语义和模块边界，包括 `BacktestContext` 删除、执行层命名收口、pack producer 真值入口归属，属于核心架构收口。
3. 如果边界不先冻结，后续很容易 quietly wrong，例如入口 guard 漂移、WF replay 与单次执行主链分叉、旧 precheck 继续误导调用方。

## 3. 任务范围

### 范围内

1. 收口 WF stitched 导出 / display 的正式分层与 Zip contract。
2. 删除 Python `validate_wf_indicator_readiness(...)` 及 workflow 对它的依赖。
3. 清理 Renko / 重复时间戳旧口径，并把 Rust stitched 检查与结构文档统一到严格递增。
4. 删除 `BacktestContext`，把 WF 的局部恢复执行收口为正式 replay 能力，而不是继续保留一个 context 壳层。
5. 统一执行层边界与命名：顶层正式入口只保留 `run_*`，内部执行器只保留 `execute_*`，样本评估 helper 只保留 `evaluate_*`；`replay` 只保留为 WF 内部步骤概念，不单独冻结成 helper 命名层。
6. 收口公开 backtest 入口命名：保留 `run_single_backtest(...)`，把 `run_backtest_engine(...)` 改为更直观的 `run_batch_backtest(...)`。
7. 明确冻结行为等价边界：核心执行主链与公开 stop / retention 语义必须等价迁移，但 precheck 删除、pack producer 收口、严格递增时间 contract 与 Renko 退出正式入口属于有意的 contract 收紧。

### 范围外

1. 不重写 `03-10` 已冻结的 warmup / window / stitched 主算法。
2. 不新增新的公开 explain / precheck API，不引入 `skip_validation`，也不新增宽泛的统一 validator 模块。
3. 不改前端或 Zip 消费端协议本身；只允许收口 Python 内部适配边界。
4. 不把 `BacktestContext` 改名保留，也不引入新的 `ExecutionArtifacts` / `WindowReplayArtifacts` 壳层。
5. 不把与上述收口目标无关的新能力顺手塞进本任务；超出本次边界的新增需求应拆成新 task。
