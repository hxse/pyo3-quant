# Pack Producer 真值入口约束

## 1. 本文只冻结两件事

本文只定义这次任务真正要改的 pack producer 规则：

1. pack object 的 producer 真值入口是谁
2. 哪些路径禁止绕过这些工具函数直接构建 pack

本文不重复展开 `build_data_pack(...)`、`build_result_pack(...)`、`extract_active(...)` 各自内部已有的对象级 contract。
这些函数的对象级 contract 以各自实现与既有契约测试为准，本文不在这里重写。

## 2. producer 真值入口

本任务冻结三个 producer 真值入口：

1. `build_data_pack(...)`
2. `build_result_pack(...)`
3. `extract_active(...)`

正式 pack object 只能通过这三个 producer 真值入口，或调用这些真值入口的正式入口来产生。

这里的“正式入口”不是开放口径。

正式入口只允许是下面两类：

1. 三个 producer 真值入口本身
2. 第 3 节明确列出的闭集 delegator

delegator 只有在同时满足下面两个条件时，才算本文中的正式入口：

1. 它只做纯参数整理、切片、编排或结果转发
2. 它在对象产出前立即强制委托到对应 producer 真值入口，且不新增对象级合法性语义

任何新增 wrapper / helper 如果不满足这两个条件，都不算本文意义上的正式入口。

## 3. 强制委托规则

### 3.1 `DataPack`

所有正式 `DataPack` 产出路径都必须最终委托给 `build_data_pack(...)`。

这包括但不限于：

1. `build_full_data_pack(...)`
2. `build_time_mapping(...)`
3. `DataPackFetchPlanner.finish(...)`
4. `slice_data_pack(...)`
5. 未来所有从 source / slice / planner 产出正式 `DataPack` 的入口

### 3.2 `ResultPack`

所有正式 `ResultPack` 产出路径都必须最终委托给 `build_result_pack(...)`。

这包括但不限于：

1. `run_single_backtest(...)`
2. `run_batch_backtest(...)` 的单项结果构建
3. WF final window result 组装
4. WF stitched result 组装
5. `slice_result_pack(...)`
6. 未来所有从阶段产物组装正式 `ResultPack` 的入口

### 3.3 active pair

所有 active 视图 pair 产出路径都必须最终委托给 `extract_active(...)`。

这包括但不限于：

1. WF active 结果提取
2. 未来所有基于同源 `DataPack + ResultPack` 的 active pair 提取路径

## 4. 禁止绕过规则

### 4.1 Python 侧

Python 侧不允许绕过 producer 真值入口直接构建 pack：

1. 不公开 `DataPack.__new__`
2. 不公开 `ResultPack.__new__`
3. 不公开 pack setter
4. Python 侧只能通过 producer 真值入口，或调用第 3 节闭集中的正式 delegator 获得 pack

### 4.2 Rust 侧

Rust 生产代码同样不允许绕过 producer 真值入口直接构建 pack：

1. 除 `build_data_pack(...)` / `build_result_pack(...)` 这类 producer 真值入口内部外，不允许直接 `DataPack::new_checked(...)`
2. 除 `build_data_pack(...)` / `build_result_pack(...)` 这类 producer 真值入口内部外，不允许直接 `ResultPack::new_checked(...)`
3. 不允许以其他旁路手造正式 pack object
4. 所有 pack 产出路径都必须收口到三个 producer 真值入口

这里的限制不只是针对 PyO3 暴露面，而是对 Rust 内外同时成立。

## 5. 本次任务必须落实的改动

这次任务在 pack producer 这一条线上必须落地：

1. 删除 Python 侧 `DataPack` / `ResultPack` 的公开构造入口
2. 删除 Python 侧 pack setter
3. 清理 Rust 生产代码中绕过工具函数的 pack 构造路径
4. 让 `active_extract.rs` 与 `slicing.rs` 回到 producer 真值入口体系
5. 正式设计中不存在共享入口 guard 支线
6. 不引入 `skip_validation` 或同义跳过语义

## 6. 最终正式口径

最终正式口径只有一句话：

**无论是 Rust 内部还是 Python 外部，正式 pack object 都只能通过 producer 真值入口，或调用第 3 节闭集中的正式 delegator 来构建。**
