# 统一 Ranges / Warmup / WF 重构总述与基础约束

本卷是整套摘要文档的共享定义入口。

这里不解释具体业务流程，只负责把后续 `02~05` 会共同依赖的真值、术语和容器约束写清楚。

## 本卷作用

1. 统一 warmup 真值链与 shared helper 的命名、公式和边界。
2. 统一 `DataPack / ResultPack / SourceRange / mapping` 的通用结构。
3. 统一时间投影工具函数、coverage 校验与 builder 收口原则。

## 分卷地图

### [01_overview_and_foundation_1_shared_resolvers_and_warmup.md](./01_overview_and_foundation_1_shared_resolvers_and_warmup.md)

负责：

1. shared resolver / helper
2. `W_resolved / W_normalized / W_applied / W_required`
3. 指标 warmup 与 backtest exec warmup 的汇合口径

适合回答的问题：

1. warmup 公式到底归哪一层定义
2. planner / WF 为什么都应该共享同一套 warmup 真值
3. 什么时候读 `W_required`，什么时候只能读容器自身 `ranges[k].warmup_bars`

### [01_overview_and_foundation_2_types_and_mapping.md](./01_overview_and_foundation_2_types_and_mapping.md)

负责：

1. `DataPack / ResultPack / SourceRange`
2. `mapping.time` 与 `ranges` 不变式
3. 时间投影工具函数
4. coverage 校验与 mapping builder

适合回答的问题：

1. 哪些字段属于容器真值
2. `mapping` 应该怎样构建与校验
3. base/source 的时间投影与覆盖约束如何统一

## 使用方式

1. 后续文档若只需要引用 warmup 真值链，直接回到分卷一。
2. 后续文档若只需要引用容器结构、时间投影或 builder 约束，直接回到分卷二。
3. 目录页只负责导航；真正的共享定义只在两个分卷正文里写一遍。

## 阅读提醒

1. 本卷里定义的是“真值如何被解释”，不是“每个流程怎样消费这份真值”。
2. 后续 `02~05` 只补局部控制流、阶段契约和失败分支，不再复制本卷公式。
3. 若某条规则会改变后续章节的控制流，后续章节仍应写出本章结论，但不重复整段定义。
