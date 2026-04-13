# `BacktestContext` 为什么该删，以及执行层要收成什么样

## 1. 乱的根源不是对象名，而是职责没拆开

当前真正混在一起的是 4 件事：

1. 公开调用想停在哪一层。
2. 内部执行从哪一层继续。
3. 已完成阶段产物要保留多少。
4. 哪些对象属于公开边界，哪些对象只属于内部执行。

`BacktestContext` 之所以难看，是因为这 4 件事都被它和 `ResultPack` 一起扛了。

## 2. 这次要收的设计意图很简单

这次执行层重构的目标不是换一个更诚实的 context 名字，而是把 single、WF、optimizer、sensitivity 都收回同一条内部执行主链。

正式方向只有 5 条：

1. `BacktestContext` 删除。
2. `ResultPack` 回到公开边界对象的位置。
3. WF 不再手动拆 single 结果再补回去，而是直接走新的内部执行起点。
4. 公开设置改名但语义保持等价，不改变现有 `execution_stage / return_only_final` 的组合行为。
5. `DataPack` / `ResultPack` 作为 formal pack object，只能由 producer 真值入口产出。

## 3. 更优雅的切法

执行层只保留一条正式内部执行器：

```text
execute_single_pipeline(...)
```

但它不再直接吃“起点 + retention + 若干 `Option carried_*`”这种松散组合。
更优雅的方向是：

1. 公开 `stop_stage + artifact_retention` 先编译成严格 `PipelineRequest`
2. `PipelineRequest` 直接编码最小输入链与目标输出 shape
3. `execute_single_pipeline(...)` 直接返回严格 `PipelineOutput`
4. `PipelineRequest -> PipelineOutput` 一一对应

这样以后：

1. single / batch 通过公开 `SettingContainer` 组装出严格 `PipelineRequest`，再交给 `execute_single_pipeline(...)`。
2. WF natural replay 走 signals 起点的严格请求。
3. WF final window 结果走 signals 起点的 full-chain 请求。
4. 已有 backtest 再算绩效的路径走 backtest 起点的严格请求。

所以 replay 不是第二套系统，而只是同一个执行器的不同请求形态。

## 4. 命名边界也一起收干净

这次一起冻结的命名层次是：

1. Rust 正式模式入口：`run_*`
2. Rust PyO3 wrapper：`py_run_*`
3. Rust 内部执行器：`execute_*`
4. Rust 内部样本评估：`evaluate_*`
5. `replay` 在这次设计里只是 WF 内部步骤概念，不额外冻结成一类通用 helper 命名

`py_run_*` 只是绑定层符号，不承担业务语义。

## 5. 为什么这比“换个 artifacts 名字继续保留”更好

如果只是把 `BacktestContext` 改成别的名字，但仍让它承担局部执行和结果回装，本质上还是旧问题。

真正干净的结构是：

1. 公开设置只描述公开 stop / retention。
2. `run_single_backtest(...)` / `run_batch_backtest(...)` 只把公开设置翻译成严格 `PipelineRequest`，自己不重复阶段编排。
3. 内部执行器只负责阶段推进。
4. 内部输出对象直接用严格 `PipelineOutput` 表达，不再用 `Option` 袋子猜测 shape。
5. 公开结果 builder 只负责对外整理。
6. pack object 的合法性真值固定收口在 producer，而不是 `run_*` 入口 guard。

公开入口命名也一起收口：

1. `run_backtest_engine(...)` 这个名字不够直观，因为它暴露了“engine”实现词，而没有表达“batch mode”。
2. `run_single_backtest(...)` 已经准确表达 single 模式，不需要再压缩。
3. 因此这次任务的更优雅收口是：保留 `run_single_backtest(...)`，把 `run_backtest_engine(...)` 改名为 `run_batch_backtest(...)`。
4. 这次值得一并做这条改名，因为它与 `stop_stage / artifact_retention` 迁移、stub 更新、结构文档更新、旧痕迹扫描高度重叠；若单独拆任务，只会拉长旧新命名双轨并增加迁移噪音。

这几件事分开以后，WF、optimizer、sensitivity 自然都会收回同一条执行主链。
