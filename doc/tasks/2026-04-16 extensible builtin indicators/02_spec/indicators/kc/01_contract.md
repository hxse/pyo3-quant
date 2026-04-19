# KC 指标契约

## 1. 指标名称

指标 base name 固定为：

```text
kc
```

`kc` 表示 Keltner Channels，中文为肯特纳通道。

## 2. 参数

正式参数：

```text
length: 正整数
scalar: 正数
```

不提供 `period` 别名。

## 3. 固定模式

KC 固定使用：

```text
tr = true
mamode = ema
```

本指标不开放 `tr` 或 `mamode` 参数。

## 4. 输入列

KC 使用同一 OHLCV source 内的：

```text
high
low
close
```

## 5. 公式

```text
TR[t] = max(
  high[t] - low[t],
  abs(high[t] - close[t-1]),
  abs(low[t] - close[t-1])
)

middle[t] = EMA(close, length)[t]
band[t] = EMA(TR, length)[t]
lower[t] = middle[t] - scalar * band[t]
upper[t] = middle[t] + scalar * band[t]
```

这里的 `band` 是 `EMA(True Range, length)`，不是仓库当前独立 `atr` 指标。

## 6. 输出列

对于实例 key `kc_x`，输出列固定为：

```text
kc_x_lower
kc_x_middle
kc_x_upper
```

输出顺序固定为：

```text
lower, middle, upper
```

## 7. warmup

```text
required_warmup_bars = length
warmup_mode = Strict
```

原因：

1. `middle` 由 `EMA(close, length)` 产生。
2. `lower / upper` 依赖 `EMA(TR, length)`。
3. `TR` 首行依赖前一根 close，因此首行缺失。
4. 多输出指标按全部输出列最大前导缺失数量定义 warmup。

## 8. 失败语义

以下情况必须直接报错：

1. `length <= 0`。
2. `scalar <= 0`。
3. 数据长度不足。
4. 缺少 `high / low / close` 任一输入列。
5. 缺少必填参数。
