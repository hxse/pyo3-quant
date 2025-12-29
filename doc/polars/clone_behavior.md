# Polars 克隆 (Clone) 行为总结

## 核心结论

**Polars 的 `DataFrame` 和 `Series` 的 `clone()` 在物理实现上是浅克隆（Shallow Clone），但在逻辑行为上表现为深克隆（Deep Clone）。**

这意味着它既拥有浅克隆的**高性能**（零拷贝），又拥有深克隆的**安全性**（数据独立，互不影响）。

## 详细机制

### 1. 物理层面：极速的“浅克隆”
当你调用 `df.clone()` 或 `s.clone()` 时，Polars **不会**复制底层的每一行数据。
*   **实现方式**：Polars 基于 Rust 实现，使用了原子引用计数（`Arc`）。`clone()` 操作仅仅是增加了底层 Apache Arrow 数组的引用计数。
*   **性能**：这是一个 $O(1)$ 的操作，消耗极少的内存和 CPU 时间，无论数据量是 100 行还是 1 亿行，克隆速度几乎一样快。

### 2. 逻辑层面：数据不可变性 (Immutability)
为什么浅克隆是安全的？
*   **Apache Arrow 后端**：Polars 的底层内存格式是 Apache Arrow，这是一种**不可变（Immutable）**的内存格式。
*   **共享内存**：由于数据不可变，多个 DataFrame 或 Series 对象共享同一块内存区域是完全安全的。读取数据时，它们看到的是完全相同的内容。

### 3. 修改行为：写时复制 (Copy-On-Write)
当你对克隆出来的 DataFrame 或 Series 进行修改（例如 `with_columns`, `append` 等）时，怎么保证不影响原对象？
*   **Copy-On-Write**：一旦你尝试修改数据，Polars 会在必要时分配新的内存来存储修改后的部分，或者构建一个新的 Arrow 数组。
*   **引用更新**：新的对象会指向这块新分配的内存，而原始对象继续指向旧的内存区域。
*   **结果**：对副本的任何修改都绝对不会污染原始数据。

## Python 接口表现

在 Python 中，Polars 将标准库的深拷贝行为映射为了自身的克隆及其高效实现：

```python
import polars as pl
import copy

df = pl.DataFrame({"a": [1, 2, 3]})
s = pl.Series("b", [4, 5, 6])

# 1. 显式调用 clone
df_clone = df.clone()
s_clone = s.clone()

# 2. 调用标准库的 deepcopy
# Polars 内部重写了 __deepcopy__ 方法，直接调用 clone()
df_deep = copy.deepcopy(df)
s_deep = copy.deepcopy(s)

# 两者不仅数据相同，而且在初始状态下共享底层内存，效率极高。
```

## 总结图示

By `hxse/pyo3-quant` team research.

```mermaid
graph TD
    A[DataFrame A] -->|指向| Data[底层数据 (Arrow Arrays)]
    B[DataFrame B \n (Clone of A)] -->|指向| Data

    note[Data 是不可变的 (Immutable)\n仅仅增加了引用计数]

    Data -.-> note

    subgraph 修改后
    A2[DataFrame A] -->|保持不变| Data
    B2[DataFrame B \n (Modified)] -->|指向新内存| NewData[新数据 / 修改后的列]
    end
```
