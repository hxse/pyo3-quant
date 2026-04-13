# Source Time 与 Renko 契约

## 0. Renko 正式边界

Renko 不属于当前仓库的正式数据生成入口。

正式边界包括：

1. 运行时入口不暴露 Renko 正式能力。
2. 配置面不暴露 Renko 正式字段。
3. 测试、示例、注释与结构文档不把 Renko 作为正式口径。

## 1. 正式 source time contract

所有进入正式执行主链的 source 都满足同一条时间列契约：

1. 必须存在 `time` 列。
2. `time` 列类型必须为 `Int64`。
3. `time` 列不允许为空。
4. `time` 列必须严格递增。

严格递增的定义是：对任意相邻两行 `i-1` 与 `i`，必须满足

```text
time[i] > time[i-1]
```

因此重复时间戳和时间回退都属于正式非法输入。

## 2. 重复时间戳的正式答案

本任务对重复时间戳 source 的正式答案是：

1. 不支持。
2. 不保留“某些入口还能构造，但后面再拒绝”的过渡状态。
3. 一旦正式入口或 stitched 检查发现重复时间戳，立即失败。

## 3. stitched 时间契约

WF stitched 结果中的各 source 也满足同一条严格递增 contract。

这条约束同时覆盖：

1. base source
2. 非 base source
3. stitched 后的 active 视图

旧的“非 base source 非递减即可”不属于正式设计。

## 4. stitched 检查的失败语义

stitched 时间检查失败时，错误信息至少应包含：

1. `source_key`
2. 问题发生的位置
3. 相邻时间值或它们的差值

错误信息的目标是让人工能直接定位是哪条 source 在哪里破坏了严格递增。

## 5. Renko 正式边界

Renko 不属于当前仓库的正式数据生成入口。

本任务冻结的边界是：

1. `renko_timeframes` 不属于正式字段。
2. `generate_renko / calculate_renko` 不属于正式对外导出。
3. “Renko 只是重复时间戳测试载体”不属于正式口径。

## 6. 测试与示例口径

正式测试与示例统一使用“一般性的重复时间戳非法输入”口径。

因此：

1. 测试注释不把 `renko_*` 当正式示例。
2. 测试辅助构造不保留 `renko_timeframes` 形态。
3. 失败 contract 直接围绕 source time contract 编写。
