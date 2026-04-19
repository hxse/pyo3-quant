# 任务范围与级别

## 任务级别

本任务按 `A 类任务` 理解。

原因：

1. 涉及共享真值链与高耦合运行边界。
2. 涉及容器结构、回测产物、WF 窗口规划与 stitched replay。
3. 若实现偏离 Spec，存在明显的 quietly wrong 风险。
4. 本任务明确采用 breaking update，并包含全仓旧桥接清理。

## 范围

本任务覆盖：

1. shared resolvers / warmup / mapping / range 真值。
2. Python 取数与 Rust 初始构建边界，其中 fetched / live formal producer 必须接入 `DataPackFetchPlanner` lifecycle。
3. `ResultPack`、active 切片与单次回测主链。
4. `WalkForwardConfig`、窗口规划、跨窗注入、窗口返回结构与 stitched 输入，其中 `run_walk_forward(...)` 入口必须校验 input readiness 与 indicator source subset。
5. segmented replay、schedule、kernel、schema 与输出口径。
6. 03-10 主链完成后的 breaking cleanup 收口。

## 非目标

本次结构重组不做以下事情：

1. 不回改 `doc/tasks/` 之外的旧文档。
2. 不把历史执行记录伪造补齐为新的 review 文档。
3. 不处理 HA、typical price、returns 等派生结果建模。
4. 不收口 `DataPack.source` 是否全局只允许 `ohlcv_*` raw source。
5. 不新增 Python 外部指标注入接口。
6. 不新增 Rust / Python 指标结果合并接口。
7. 不修改当前 signal 对外引用指标列的语义。

## 正式文档入口

1. [04_fetched_live_formal_producer_context.md](../01_context/04_fetched_live_formal_producer_context.md)
2. [06_fetched_live_formal_producer_and_wf_readiness.md](../02_spec/06_fetched_live_formal_producer_and_wf_readiness.md)
3. [08_fetched_live_formal_producer_execution_plan.md](../03_execution/08_fetched_live_formal_producer_execution_plan.md)

## 当前状态

1. `03-10` 是统一 ranges / warmup / WF 的 A 类任务快照。
2. 当前正式范围已覆盖 fetched / live formal producer、参数冻结顺序与 `WF` 入口 readiness 防线。
3. 已完成执行结果仍以 `04_review/01_post_execution_review.md`、`04_review/04_execution_backfill_template.md` 与当前源码为准。
4. 尚未落地的 fetched / live producer 接线与 `WF` readiness 修复，以本文件列出的正式文档和执行计划为后续实施入口。

## 结构映射

本次仅做目录职责重组：

1. 原 `01_summary` 主体内容移动到 `02_spec`。
2. 原 `02_execution` 主体内容移动到 `03_execution`。
3. 原执行回填模板移动到 `04_review`。
4. 新增 `00_meta` 与 `01_context` 作为当前规范下的入口层。
