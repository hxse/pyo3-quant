# Polars 中 NaN 与 null 的行为差异

## 概述

在 Polars 中，`NaN`（Not a Number）和 `null`（缺失值）是两种完全不同的特殊值，它们在比较操作中的行为截然不同。理解这种差异对于正确处理信号生成器至关重要。

## 核心差异

| 特性 | NaN | null |
|------|-----|------|
| **类型** | 浮点数特殊值 | 表示缺失数据 |
| **null_count()** | 0（不算作 null） | 计入 null 统计 |
| **比较行为** | 返回确定的 true/false | 传播 null（结果也是 null） |
| **比较语义** | 被视为"最大值" | 表示"未知" |
| **fill_null() 有效** | ❌ 无效 | ✅ 有效 |
| **填充方法** | 使用 `fill_nan()` | 使用 `fill_null()` |
| **统计方法** | `is_nan().fill_null(False).sum()` | `null_count()` |

## 详细测试结果

### Part 1: NaN 的行为

#### 测试数据
```python
series_with_nan = pl.Series("with_nan", [np.nan, np.nan, np.nan])
series_normal = pl.Series("normal", [100.0, 105.15, 110.0])
```

#### 关键发现

**1. NaN 不被视为 null**
```python
series_with_nan.null_count()  # 返回 0
series_with_nan.is_null()     # 全部返回 false
```

**2. NaN 在比较中被视为"最大值"**
```python
# 正常值 < NaN → 全部为 true
normal < with_nan  # [true, true, true]

# NaN > 正常值 → 全部为 true
with_nan > normal  # [true, true, true]

# NaN < 正常值 → 全部为 false
with_nan < normal  # [false, false, false]
```

**3. NaN == NaN 返回 true（与 IEEE 754 不同！）**
```python
with_nan == with_nan  # [true, true, true]
```

> ⚠️ **重要**：这与 IEEE 754 标准和原生 Python/NumPy 的行为不同！
> 在原生 Python 中：`np.nan == np.nan` 返回 `False`
> 在 Polars 中：`NaN == NaN` 返回 `True`

**4. fill_null() 对 NaN 无效**
```python
result = normal < with_nan  # [true, true, true]
result.fill_null(False)     # 仍然是 [true, true, true]，没有变化
```

### Part 2: null 的行为

#### 测试数据
```python
series_with_null = pl.Series("with_null", [100.0, None, 110.0])
series_normal2 = pl.Series("normal2", [100.0, 105.15, 110.0])
```

#### 关键发现

**1. null 被正确识别**
```python
series_with_null.null_count()  # 返回 1
series_with_null.is_null()     # [false, true, false]
```

**2. null 在比较中传播**
```python
# 正常值 < null → 包含 null 的位置也返回 null
normal2 < with_null  # [false, null, false]

# null < 正常值 → 包含 null 的位置也返回 null
with_null < normal2  # [false, null, false]
```

**3. null == null 返回 null（不是 true！）**
```python
with_null == with_null  # [true, null, true]
```

**4. fill_null() 对 null 有效**
```python
result = normal2 < with_null  # [false, null, false]
result.fill_null(False)       # [false, false, false]，null 被填充了
```

## 实际影响：信号生成器的问题

### 问题场景

在多周期策略中，大周期指标（如 `sma_1` 来自 4h 数据）会有前导 NaN 值。当小周期的 `sma_0` 有值而 `sma_1` 仍是 NaN 时：

```python
# 假设：
sma_0 = 105.15  # 有效值
sma_1 = NaN     # 大周期尚未计算出值

# 信号条件：sma_0 < sma_1
# Polars 计算：105.15 < NaN → true（因为 NaN 被视为最大值）
# 结果：错误地触发了做多信号！
```

### 为什么会出现这个问题

1. **代码假设**：原始代码假设 Polars 的 NaN 和 null 都会传播，即包含特殊值的比较结果应该是"无效"的
2. **实际行为**：Polars 将 NaN 视为"最大值"，比较会返回确定的 true/false
3. **后果**：在大周期指标尚未计算出有效值（仍为 NaN）时，小周期已经错误地触发了信号

### 解决方案

在信号生成器的比较操作中，需要显式检测并过滤 NaN：

```rust
// 执行比较后，检测是否包含 NaN
let mut result = perform_comparison(...)?;

// 如果左侧或右侧包含 NaN，将对应位置的结果设为 false
let left_is_nan = left.is_nan()?;
let right_is_nan = right.is_nan()?;
let has_nan = left_is_nan.bitor(right_is_nan);

result = result.bitand(has_nan.not());
```

### 验证案例：1h vs 4h 数据对齐

测试脚本中的 **Part 9** 模拟了真实的 4H SMA 与 1H 数据对齐场景：

**数据场景**：
- 1H 周期 (`sma_1h`)：连续有效值 `[100.0, 101.0, 102.0, 103.0, ...]`
- 4H 周期 (`sma_4h`)：前导 NaN `[NaN, NaN, NaN, NaN, 102.5, ...]`

**错误结果 (直接比较)**：
```python
# sma_1h < sma_4h
[true, true, true, true, false, ...]
# 错误！前4个点因为 NaN 被视为最大值而触发 true
```

**正确结果 (过滤 NaN)**：
```python
# (sma_1h < sma_4h) & ~has_nan
[false, false, false, false, false, ...]
# 正确！前4个点被过滤为 false
```

## 混合场景测试结果

### 测试数据
```python
series_mixed = pl.Series("mixed", [100.0, np.nan, None, 110.0, np.nan, None])
```

### 关键发现

**1. is_nan() 在 null 位置会传播 null**
```python
series_mixed.is_nan()   # [false, true, null, false, true, null]
series_mixed.is_null()  # [false, false, true, false, false, true]
```
> ⚠️ **重要**：`is_nan()` 对 null 值返回 null（不是 false！）

**2. 删除操作是独立的**
```python
# drop_nulls() 只删除 null，保留 NaN
series_mixed.drop_nulls()  # [100.0, NaN, 110.0, NaN]

# drop_nans() 只删除 NaN，保留 null
series_mixed.drop_nans()   # [100.0, null, 110.0, null]

# 要全部删除需要链式调用
series_mixed.drop_nulls().drop_nans()  # [100.0, 110.0]
```

**3. 填充操作也是独立的**
```python
# fill_null() 只填充 null，NaN 保持不变
series_mixed.fill_null(-999.0)  # [100.0, NaN, -999.0, 110.0, NaN, -999.0]

# fill_nan() 只填充 NaN，null 保持不变
series_mixed.fill_nan(-888.0)   # [100.0, -888.0, null, 110.0, -888.0, null]

# 同时填充需要链式调用
series_mixed.fill_nan(-888.0).fill_null(-999.0)
# [100.0, -888.0, -999.0, 110.0, -888.0, -999.0]
```

**4. 统一转换模式（推荐）**
```python
# 模式1: 将 NaN 转为 null，然后统一处理
series_mixed.fill_nan(None).forward_fill()  # 向前填充
series_mixed.fill_nan(None).interpolate()   # 线性插值
```

### NaN 统计方法 (Part 6 发现)

由于 `is_nan()` 在 null 位置会返回 null，统计 NaN 数量需要特别注意：

```python
# ❌ 不推荐：结果可能为 null 或不准确
count = series.is_nan().sum()

# ✅ 推荐：填充 null 后再统计
count = series.is_nan().fill_null(False).sum()
```

### DataFrame 级别操作 (Part 7 发现)

在 DataFrame 级别处理时，可以使用表达式来高效处理：

**1. 统计每列的 NaN**
```python
# 遍历列进行统计
for col in df.columns:
    nan_count = df[col].is_nan().fill_null(False).sum()
```

**2. 筛选包含 NaN 的行**
```python
# 使用 any_horizontal
df.filter(
    pl.any_horizontal([pl.col(c).is_nan().fill_null(False) for c in df.columns])
)
```

**3. DataFrame 表达式模式**
```python
# 推荐使用表达式同时处理 NaN 和 null
df.with_columns(
    signal = (
        (pl.col("val") < pl.col("threshold")).fill_null(False)
        & ~pl.col("val").is_nan().fill_null(False)
        & ~pl.col("threshold").is_nan().fill_null(False)
    )
)
```

## 完整对比表

| 操作 | 对 NaN 的行为 | 对 null 的行为 | 备注 |
|------|--------------|----------------|------|
| **检测** | | | |
| `null_count()` | 不计数（返回 0） | 计入统计 | NaN 不被视为 null |
| `is_null()` | 返回 false | 返回 true | 准确识别 |
| `is_nan()` | 返回 true | 返回 null ⚠️ | is_nan 对 null 会传播！ |
| **比较** | | | |
| `a < NaN` | true | - | NaN 被视为最大值 |
| `NaN > a` | true | - | NaN 被视为最大值 |
| `NaN == NaN` | true | - | 与 IEEE 754 不同！ |
| `a < null` | - | null | null 会传播 |
| `null == null` | - | null | null 会传播 |
| **删除** | | | |
| `drop_nulls()` | 保留 | 删除 | 只处理 null |
| `drop_nans()` | 删除 | 保留 | 只处理 NaN |
| **填充** | | | |
| `fill_null(value)` | 无效（保留） | 填充为 value | 只处理 null |
| `fill_nan(value)` | 填充为 value | 无效（保留） | 只处理 NaN |
| `fill_nan(None)` | 转为 null | 保持 null | 统一转换 ✅ |
| `forward_fill()` | 无效（保留） | 用前值填充 | 只对 null 有效 |
| `backward_fill()` | 无效（保留） | 用后值填充 | 只对 null 有效 |
| `interpolate()` | 无效（保留） | 线性插值 | 只对 null 有效 |

## 最佳实践

### 1. 区分使用场景
- **null**：表示真正的缺失数据（如数据源没有提供）
- **NaN**：表示计算结果未定义（如 0/0、sqrt(-1) 等）

### 2. 信号生成器处理原则
对于条件判断，应将包含 NaN 的比较视为"无效"：
```rust
// ❌ 错误：直接比较，NaN 会被视为最大值
let result = left.gt(right)?;

// ✅ 正确：显式检测并过滤 NaN
let result = left.gt(right)?;
let left_is_nan = left.is_nan()?;
let right_is_nan = right.is_nan()?;
let has_nan = left_is_nan.bitor(right_is_nan);
result = result.bitand(has_nan.not());
```

### 3. 数据清洗策略

**策略 A：分别处理（明确控制）**
```python
# 适用于 NaN 和 null 需要不同处理方式的情况
df = df.fill_nan(-888.0).fill_null(-999.0)
```

**策略 B：统一转换（推荐）**
```python
# 将 NaN 转为 null，然后统一处理
df = df.fill_nan(None).interpolate()  # 插值
df = df.fill_nan(None).forward_fill()  # 向前填充
```

**策略 C：全部删除**
```python
# 删除所有特殊值
df = df.drop_nans().drop_nulls()
```

### 4. 调试技巧
```python
# 检查数据中的特殊值
print(f"null 数量: {series.null_count()}")

# ✅ 准确的 NaN 统计（排除 null）
nan_count = series.is_nan().fill_null(False).sum()
print(f"纯 NaN 数量: {nan_count}")

# 查看特殊值的位置 (含 DataFrame 筛选)
df.filter(pl.col("col").is_nan().fill_null(False))
```

## 常见陷阱

### 陷阱 1: is_nan() 对 null 返回 null
```python
series = pl.Series([1.0, np.nan, None])
series.is_nan()  # [false, true, null]  ← 注意第三个是 null！

# 解决方案：如果需要 boolean，需要填充
series.is_nan().fill_null(False)  # [false, true, false]
```

### 陷阱 2: NaN 比较不会传播
```python
# ❌ 错误假设：认为 NaN 比较会返回 null
series_with_nan < 100  # 返回 [true, true, true]（如果 series 全是 NaN）

# ✅ 正确：显式检测 NaN
mask = series_with_nan.is_nan().fill_null(True)
valid_comparison = (series_with_nan < 100) & ~mask
```

### 陷阱 3: 只用一种填充方法
```python
# ❌ 错误：只用 fill_null()，NaN 没有被处理
df.fill_null(0)  # NaN 仍然存在！

# ✅ 正确：根据需要选择策略
df.fill_nan(None).fill_null(0)  # 明确处理两种情况
```

## 参考

- 测试脚本：[`py_entry/minimal_working_example/test_nan_behavior.py`](file:///home/hxse/pyo3-quant/py_entry/minimal_working_example/test_nan_behavior.py)
- 信号生成器代码：[`src/backtest_engine/signal_generator/condition_evaluator.rs`](file:///home/hxse/pyo3-quant/src/backtest_engine/signal_generator/condition_evaluator.rs)
