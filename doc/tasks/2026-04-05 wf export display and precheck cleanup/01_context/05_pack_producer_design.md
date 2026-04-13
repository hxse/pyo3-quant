# 为什么要禁止绕过工具函数构建 pack

## 1. 这次真正要收的不是 validator

这次任务在 pack 这一层的关键问题，不是“要不要再补一个共享 guard”，而是：

**pack object 到底能不能被绕过正式工具函数直接手造。**

如果 `DataPack` / `ResultPack` 仍然允许在 Python 或 Rust 生产代码里被自由构造，那么 pack 的合法性真值就永远落不到对象生产面，只能继续漂在入口兜底、precheck 或额外 validator 上。

这条路本质上是把风险留给调用方，不够干净。

## 2. 最终收口原则

这次任务在 pack 这一层冻结一条硬约束：

**禁止绕过 producer 真值入口构建 pack。**

这不是“推荐写法”，而是正式边界。它同时覆盖：

1. Python 侧不允许直接 `DataPack(...)` / `ResultPack(...)`
2. Python 侧不允许通过 setter 改写 pack
3. Rust 生产代码除 producer 真值入口内部外，不允许直接 `DataPack::new_checked(...)` / `ResultPack::new_checked(...)`
4. Rust 生产代码不允许通过任何其他旁路手造正式 pack object

也就是说，限制不是只对 PyO3 暴露面成立，而是对 Rust 内外同时成立。

## 3. 为什么这比入口 guard 更优雅

一旦 pack 只能由 producer 真值入口产出：

1. pack 的合法性真值自然收回 producer 自身
2. `run_*` 入口不需要再承担额外兜底
3. Python precheck、共享 guard、`skip_validation` 这类支线语义就没有继续存在的必要
4. builder 内已有的校验可以继续作为唯一真值，不需要在入口层复制第二套

所以这次更优雅的方向不是“再补一个 validator”，而是从根上禁止绕过工具函数构建 pack。

## 4. 为什么 producer 真值入口是三个

这次接受的正式真值入口有且只有三类：

1. `build_data_pack(...)`
2. `build_result_pack(...)`
3. `extract_active(...)`

前两个是构造正式 `DataPack` / `ResultPack` 的真值入口。

`extract_active(...)` 保留为第三个真值入口，是因为它表达的不是普通 constructor，而是：

同源 `DataPack + ResultPack` -> active 视图 `DataPack + ResultPack`

这是正式的 pair-transform 语义。把它硬压回普通 build 流程，只会把真实语义抹平。

## 5. 其他入口的正确位置

一旦这三个真值入口冻结下来，其余所有会产出 pack 的入口都只能做两件事：

1. 作为更高层 helper 或模式入口存在
2. 最终委托给这三个真值入口之一

它们不再拥有自行手造 pack 的资格。

换句话说，这次任务的先后顺序应当是：

1. 先把 Rust 内部真值入口收干净
2. 再删除 Python 侧公开构造与 setter
3. 最终形成“Rust 内外都不能绕过工具函数构建 pack”的单一正式口径

## 6. 这篇 context 真正要表达的设计意图

这次 pack 层设计的核心品味不是“多写一层校验”，而是：

1. `DataPack` / `ResultPack` 继续作为正式类型存在
2. 但它们不再是自由构造对象
3. producer 真值入口才是 pack 真值入口
4. Rust 内外都禁止绕过这些工具函数直接构建 pack
5. 真值收口到 producer，自然替代入口 guard 这条思路
