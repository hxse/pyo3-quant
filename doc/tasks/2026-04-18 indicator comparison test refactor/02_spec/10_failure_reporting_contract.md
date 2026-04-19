# Failure Reporting Contract

## 1. 目标

指标对齐阶段可能出现大量失败。

失败信息必须足够定位问题，但不能打印过长日志。

## 2. 必填上下文

每个失败必须报告：

1. 校验模式：primary、secondary expected same、secondary expected different、local CSV exact、local CSV similarity。
2. 指标 base name。
3. indicator key。
4. 输出列。
5. 参数。
6. dataset source：`DatasetId` 或 `Path`。
7. source key。
8. oracle。
9. 失败行号。
10. 若有 time 列，打印失败行 time。
11. engine 值。
12. oracle 值。
13. tolerance。
14. 缺失值 mask 状态。

## 3. 数据上下文

失败时应打印失败点附近的短上下文。

默认上下文窗口：

```text
前 3 行 + 失败行 + 后 3 行
```

最大不超过 7 行。

上下文只打印必要列：

1. `time`
2. engine 输出列
3. oracle 输出列
4. engine missing mask
5. oracle missing mask
6. diff

## 4. 不同失败类型

长度不一致：打印双方长度。

列缺失：打印缺失列名和可用列名摘要。

缺失值 mask 不一致：打印第一个 mask 不一致位置及短上下文。

数值不一致：打印第一个超出容差的位置、差值、容差和短上下文。

expected different 失败：说明目标范围被 same comparator 判定为一致，并打印检查范围摘要。

local CSV similarity 失败：打印相似性 API、实际分数、阈值和短上下文。
