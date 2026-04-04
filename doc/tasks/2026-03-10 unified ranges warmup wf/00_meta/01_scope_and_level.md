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
2. Python 取数与 Rust 初始构建边界。
3. `ResultPack`、active 切片与单次回测主链。
4. `WalkForwardConfig`、窗口规划、跨窗注入、窗口返回结构与 stitched 输入。
5. segmented replay、schedule、kernel、schema 与输出口径。
6. 03-10 主链完成后的 breaking cleanup 收口。

## 非目标

本次结构重组不做以下事情：

1. 不重写 `03-10` 原有 Spec 逻辑。
2. 不把历史快照全文改写成最新文风。
3. 不回改 `doc/tasks/` 之外的旧文档。
4. 不把历史执行记录伪造补齐为新的 review 文档。

## 当前状态

1. `03-10` 作为历史 A 类任务，已完成。
2. 当前完成态真值以 `04_review/01_post_execution_review.md`、`04_review/04_execution_backfill_template.md` 与当前源码为准。
3. 本次文档变更只做结构重组与职责归位，不改写既有 `02_spec` 主干真值。

## 结构映射

本次仅做目录职责重组：

1. 原 `01_summary` 主体内容移动到 `02_spec`。
2. 原 `02_execution` 主体内容移动到 `03_execution`。
3. 原执行回填模板移动到 `04_review`。
4. 新增 `00_meta` 与 `01_context` 作为当前规范下的入口层。
