# 真值源与对齐标准

## 1. 默认真值源

所有内置指标默认以原版 `pandas-ta` 对齐。

只有在原版 `pandas-ta` 确实缺失目标指标或目标模式时，才允许按项目指标优先级后退。

## 2. 指标对齐优先级

正式优先级固定为：

1. `pandas-ta (talib=true)`
2. `pandas-ta (talib=false)`
3. `pandas-ta-classic (talib=true)`
4. `pandas-ta-classic (talib=false)`

原始 `talib` 不作为正式真值源。

## 3. 测试调用方式

测试中应统一使用：

```python
import pandas_ta as ta
ta.xxx(...)
```

不得使用：

```python
ohlc.ta.xxx(...)
```

## 4. 缺失处理

若原版 `pandas-ta` 缺失目标指标：

1. 必须在该指标的 `02_spec/indicators/<name>/` 中说明缺失事实。
2. 必须写明后退到哪一级真值源。
3. 必须说明可能的行为差异和测试覆盖方式。

## 5. 偏差处理

若实现过程中发现已有指标与正式真值源不一致，不允许在新增指标任务中顺手修改。

处理方式：

1. 在 review 中记录偏差。
2. 判断是否影响当前指标。
3. 必要时拆出单独指标修复任务。
