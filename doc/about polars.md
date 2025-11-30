
## 💡 关于 Polars 的易混淆点：可变性差异

在使用 Polars 时，其 Python API (PyPolars) 和 Rust Eager API 在数据帧 (DataFrame) 的修改模式上存在根本差异，这对于编写高性能代码至关重要。

| 特性 | Python API (PyPolars) | Rust Eager API |
| :--- | :--- | :--- |
| **方法名示例** | `df.with_columns(...)` | `df.with_column(...)` |
| **设计模式** | 逻辑上**不可变** (Immutable) | **原地修改** (In-place Mutation) |
| **返回值** | 总是返回**新的 DataFrame 对象** | 接收 `&mut self`，返回 `Result<Self, ...>` |
| **底层实现** | 基于 **Copy-on-Write (零拷贝)** 优化，保证了高效的不可变性。 | **直接修改**内存数据，追求绝对的修改性能。 |
| **典型用法** | 必须使用**变量遮蔽**：<br>`df = df.with_columns(...)` | 必须使用**可变变量**：<br>`let mut df = ...;`<br>`df.with_column(...)?;` |

### 🔑 根本差异 (Key Takeaway)

* **Python 的不可变性**：是一种**高效的哲学**，通过 Copy-on-Write 实现了类似函数式编程的简洁和数据安全，同时保持高性能。
* **Rust Eager API 的 `with_column`**：是**特例**，采用 `&mut self` 是为了在 Rust 原生环境中追求**最高性能和操作简洁性**，避免了额外的变量赋值和所有权转移。
