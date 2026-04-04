# 全仓旧桥接清理与最终破坏性收口补充执行计划（历史）

对应文档：

1. [../00_meta/task_summary.md](../00_meta/task_summary.md)
2. [../02_spec/03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)
3. [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
4. [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)
5. [01_execution_plan.md](./01_execution_plan.md)
6. [02_test_plan.md](./02_test_plan.md)
7. [03_execution_stages_and_acceptance.md](./03_execution_stages_and_acceptance.md)
8. [05_pre_execution_ai_review.md](./05_pre_execution_ai_review.md)

本文定位：

1. 本文不是新任务，也不是重新定义 `03-10` 摘要。
2. 本文记录的是当时为清理全仓旧桥接、旧壳层与旧兼容路径而补立的执行计划。
3. 当前仓库的完成态真值，以 `04_review/01_post_execution_review.md`、`04_review/04_execution_backfill_template.md` 与当前源码为准。
4. 因此本文后续出现的“残留事实 / 删除项 / 阶段动作”，都按历史立项语境理解，不再作为当前仓库现状描述。
5. 本文保留在 `03_execution`，只作为 `03-10` 当时的补充执行计划归档。

## 0. 立项时背景（历史）

当时 `walk_forward / stitched` 主链已经切到正式 `pack/result` 语义，但全仓仍有三类旧残留：

1. 公开 API 残留：
   - `src/backtest_engine/top_level_api.rs`
   - `python/pyo3_quant/backtest_engine/__init__.pyi`
   - `python/pyo3_quant/_pyo3_quant/__init__.pyi`
   这些文件仍公开 `DataContainer -> BacktestSummary` 的旧输入输出口径。
2. 私有桥接残留：
   - `src/backtest_engine/top_level_api.rs`
   - `py_entry/runner/results/wf_result.py`
   这些文件仍存在 `DataPack -> DataContainer`、`ResultPack -> BacktestSummary` 的回桥函数。
3. 运行时与测试残留：
   - `src/types/inputs/data.rs`
   - `src/types/outputs/backtest.rs`
   - `src/backtest_engine/indicators/*`
   - `src/backtest_engine/signal_generator/*`
   - `src/backtest_engine/optimizer/*`
   - `src/backtest_engine/sensitivity/*`
   - `py_entry/runner/*`
   - `py_entry/charts/*`
   - `py_entry/io/*`
   - `py_entry/Test/*`
   这些路径仍不同程度依赖 `DataContainer` 或 `BacktestSummary`。

因此，立项当时状态只能算：

1. `03-10` 的 `WF / stitched` 主线已经完成。
2. 整个项目还没有完成“全量破坏性更新”。

## 1. 本文执行目标

本次补充执行只做一件事：

1. 删除整个项目里所有不再需要的旧桥接、旧壳层、旧兼容，使全仓唯一正式类型收口到新主链。

完成标准：

1. `DataContainer` 从 Rust 类型、PyO3 导出、Python 导入、运行时对象、测试对象中全部移除。
2. `BacktestSummary` 从 Rust 类型、PyO3 导出、Python 导入、运行时对象、测试对象中全部移除。
3. 单次回测、批量回测、优化、敏感性、WF、图表、导出、scanner、测试工具全部统一消费 `DataPack / ResultPack`。
4. 不保留旧属性别名，不保留旧函数别名，不保留旧桥接 helper，不保留“新旧双轨都能用”的过渡层。
5. `just check` 与 `just test` 全量通过。

## 2. 最终态约束

### 2.1 唯一正式输入输出

1. 输入侧唯一正式容器是 `DataPack`。
2. 输出侧唯一正式结果是 `ResultPack`。
3. 时间/预热/有效段唯一正式范围对象是 `SourceRange`。
4. WF 窗口与 stitched 元数据唯一正式对象是：
   - `WindowMeta`
   - `WindowArtifact`
   - `StitchedMeta`
   - `StitchedArtifact`
   - `NextWindowHint`

### 2.2 明确删除项

以下对象在本次完成后必须不存在于代码主链：

1. `DataContainer`
2. `BacktestSummary`
3. `data_pack_to_legacy_container(...)`
4. `result_pack_to_summary(...)`
5. `_data_pack_to_container(...)`
6. `_result_pack_to_summary(...)`
7. 任何 `summary=` 风格的 Python 运行结果对象初始化
8. 任何 `data_dict=` 风格的 Python 运行结果对象初始化

### 2.3 PyO3 与 stub 最终态

1. Rust 是唯一类型源头。
2. `.pyi` 只能由 Rust 真实公开类型生成。
3. 不手写镜像 `.pyi`。
4. 对外函数名若继续保留原名，只允许直接切签名，不允许新增 `*_v2`、`*_pack`、`*_legacy` 这类并行公开 API。
5. Python 侧不保留 “旧属性名 -> 新属性名” 的兼容 property。

## 3. 破坏性更新清单

### 3.1 Rust 类型层

必须直接删除：

1. `src/types/inputs/data.rs` 里的 `DataContainer`
2. `src/types/outputs/backtest.rs` 里的 `BacktestSummary`
3. `src/types/inputs/mod.rs`、`src/types/outputs/mod.rs`、`src/types/mod.rs` 中对旧类型的 re-export
4. `src/lib.rs` 中对旧类型的 `m.add_class::<...>()`

### 3.2 Rust 公开函数层

必须直接切成最终态：

1. `run_single_backtest(data: DataPack, ...) -> ResultPack`
2. `run_backtest_engine(data: DataPack, ...) -> Vec<ResultPack>`
3. 相关 optimizer / sensitivity / performance / indicators / signal_generator 的 PyO3 入口同步切到 `DataPack / ResultPack`

要求：

1. 保留函数名，不保留旧签名。
2. 不新增平行入口。
3. 不新增 facade 再回桥到旧对象。

### 3.3 Python 运行时层

必须直接切成最终态：

1. `py_entry/runner/backtest.py`
   - `self.data_dict` 改为 `self.data_pack`
   - `run()` 返回对象不再持有 `summary`
2. `py_entry/runner/results/run_result.py`
   - 主对象字段从 `summary / data_dict` 改为 `result / data_pack`
3. `py_entry/runner/results/batch_result.py`
   - 批量结果统一持有 `list[ResultPack]`
4. `py_entry/runner/results/wf_result.py`
   - 不再把 stitched `DataPack / ResultPack` 投影回旧对象
5. `py_entry/charts/*`
   - 图表输入统一改为 `DataPack / ResultPack`
6. `py_entry/io/*`
   - 导出、转换、bundle 统一改为 `DataPack / ResultPack`
7. `py_entry/scanner/strategies/base.py`
   - scanner 侧输出统一改为 `DataPack`

要求：

1. 运行时对象只允许暴露 `data_pack` 正式字段。
2. 运行时对象只允许暴露 `result` 正式字段。
3. 不保留“如果传旧对象就自动转新对象”的分支。

### 3.4 `data_ops` 最终态

旧 `DataContainer / BacktestSummary` 工具链必须收口：

1. 若某工具仍然有业务价值，就改到 `DataPack / ResultPack`。
2. 若某工具只是旧壳层辅助，就直接删除。

明确约束：

1. 不保留 `slice_data_container(...)`
2. 不保留 `slice_backtest_summary(...)`
3. 不保留 `concat_backtest_summaries(...)`
4. 允许存在的新工具只能是面向正式对象的版本，例如：
   - `slice_data_pack(...)`
   - `slice_result_pack(...)`
   - `concat_result_packs(...)`
5. 若 `extract_active(...)` 已经覆盖该职责，则优先删除旧切片工具，而不是再造一组平行 pack 版 API。

## 4. 模块落地范围

### 4.1 必改 Rust 模块

1. `src/types/inputs/data.rs`
2. `src/types/inputs/mod.rs`
3. `src/types/outputs/backtest.rs`
4. `src/types/outputs/mod.rs`
5. `src/types/mod.rs`
6. `src/lib.rs`
7. `src/backtest_engine/top_level_api.rs`
8. `src/backtest_engine/indicators/mod.rs`
9. `src/backtest_engine/signal_generator/mod.rs`
10. `src/backtest_engine/signal_generator/group_processor.rs`
11. `src/backtest_engine/signal_generator/operand_resolver.rs`
12. `src/backtest_engine/signal_generator/condition_evaluator/mod.rs`
13. `src/backtest_engine/performance_analyzer/mod.rs`
14. `src/backtest_engine/optimizer/evaluation.rs`
15. `src/backtest_engine/optimizer/runner/mod.rs`
16. `src/backtest_engine/optimizer/py_bindings.rs`
17. `src/backtest_engine/sensitivity/runner.rs`
18. `src/backtest_engine/data_ops/mod.rs`
19. `src/backtest_engine/utils/context.rs`
20. `src/backtest_engine/utils/memory_optimizer.rs`

### 4.2 必改 Python 模块

1. `py_entry/types/__init__.py`
2. `py_entry/runner/setup_utils.py`
3. `py_entry/runner/backtest.py`
4. `py_entry/runner/results/run_result.py`
5. `py_entry/runner/results/batch_result.py`
6. `py_entry/runner/results/wf_result.py`
7. `py_entry/charts/_generation_core.py`
8. `py_entry/charts/_generation_panels.py`
9. `py_entry/charts/_generation_bottom.py`
10. `py_entry/io/_converters_bundle.py`
11. `py_entry/io/_converters_result.py`
12. `py_entry/scanner/strategies/base.py`

### 4.3 必改 stub 与测试

1. `python/pyo3_quant/_pyo3_quant/__init__.pyi`
2. `python/pyo3_quant/backtest_engine/__init__.pyi`
3. `python/pyo3_quant/backtest_engine/data_ops/__init__.pyi`
4. `python/pyo3_quant/backtest_engine/optimizer/__init__.pyi`
5. `python/pyo3_quant/backtest_engine/sensitivity/__init__.pyi`
6. `python/pyo3_quant/backtest_engine/walk_forward/__init__.pyi`
7. `py_entry/Test/backtest/common_tests/test_top_level_api_validation.py`
8. `py_entry/Test/data_generator/test_data_ops_tools.py`
9. `py_entry/Test/test_public_api_stub_contract.py`
10. 所有仍显式导入旧类型的测试文件

## 5. 分阶段执行

### 阶段 A：先切类型与公开边界

目标：

1. 先把旧类型从类型层和公开导出层拿掉。
2. 让编译报错主动暴露全仓剩余旧依赖。

动作：

1. 删除 `DataContainer`
2. 删除 `BacktestSummary`
3. 修改所有公开函数签名
4. 更新 `src/lib.rs` 导出
5. 运行 `just check`

阶段放行标准：

1. `src`、`py_entry`、`python` 里不再存在旧类型定义
2. `just check` 通过

### 阶段 B：再切 Rust 内部消费链

目标：

1. 把指标、信号、回测、绩效、优化、敏感性全部改为正式对象。
2. 删除 `top_level_api.rs` 私有桥接。

动作：

1. 所有以市场数据为输入的模块统一改收 `&DataPack`
2. 所有以阶段结果为返回的公开对象统一改为 `ResultPack`
3. 删除旧 bridge helper
4. 重写必要的切片/拼接 helper
5. 运行 `just check`

阶段放行标准：

1. `rg -n "\\bDataContainer\\b|\\bBacktestSummary\\b" src` 无结果
2. `rg -n "data_pack_to_legacy_container|result_pack_to_summary" src` 无结果
3. `just check` 通过

### 阶段 C：再切 Python 运行时与展示导出链

目标：

1. 把 Python 上层对象名、字段名、图表输入、导出输入一次性切成最终态。

动作：

1. `Backtest` 改持有 `data_pack`
2. `RunResult` 改持有 `result / data_pack`
3. `BatchResult`、`WalkForwardResultWrapper`、charts、io、scanner 全部同步改名
4. 删除全部 Python 回桥 helper
5. 运行 `just check`

阶段放行标准：

1. `rg -n "\\bDataContainer\\b|\\bBacktestSummary\\b" py_entry python` 只允许命中文档注释或历史任务文档之外的零结果
2. `rg -n "_data_pack_to_container|_result_pack_to_summary" py_entry` 无结果
3. `just check` 通过

### 阶段 D：最后切 stub、测试与文档回填

目标：

1. 让对外公开面、类型存根、测试口径与源码完全一致。

动作：

1. 跑 `just stub`
2. 更新所有受影响测试
3. 新增 absence contract：
   - 旧类型不再出现在 `.pyi`
   - 旧桥接 helper 不再出现在运行时代码
4. 运行 `just check`
5. 运行 `just test`

阶段放行标准：

1. `just check` 通过
2. `just test` 通过
3. 公共 stub 不再导出旧类型

## 6. 测试与 gate

### 6.1 静态清理 gate

必须新增或保留以下检查：

1. `rg -n "\\bDataContainer\\b|\\bBacktestSummary\\b" src py_entry python`
2. `rg -n "data_pack_to_legacy_container|result_pack_to_summary|_data_pack_to_container|_result_pack_to_summary" src py_entry python`
3. `rg -n "run_single_backtest\\(|run_backtest_engine\\(" python/pyo3_quant/backtest_engine/__init__.pyi src/backtest_engine/top_level_api.rs`

验收口径：

1. 第 `1`、`2` 条在代码目录必须为零结果。
2. 第 `3` 条允许命中，但签名必须已经切到 `DataPack / ResultPack`。

### 6.2 运行 gate

执行顺序固定：

1. `just check`
2. `just test`

建议补跑的最小 Python gate：

1. `just test-py path="py_entry/Test/test_public_api_stub_contract.py"`
2. `just test-py path="py_entry/Test/backtest/common_tests/test_top_level_api_validation.py"`
3. `just test-py path="py_entry/Test/walk_forward/test_walk_forward_guards.py"`

建议补跑的最小 Rust gate：

1. `just test-rust-exact backtest_engine::walk_forward::next_window_hint::tests::test_next_window_hint_contract`
2. `just test-rust-exact backtest_engine::walk_forward::stitch::tests::test_stitched_replay_input_contract`
3. `just test-rust-exact backtest_engine::data_ops::warmup_requirements::tests::test_ignore_indicator_warmup_contract`

## 7. AI 执行注意事项

1. 这是最终收口任务，不是迁移任务。
2. 遇到“这条旧 API 还可能有人用”的判断时，默认直接切断，不额外保留兼容层。
3. 若某个 Python 包装对象已经没有存在必要，就直接删，不为了“调用方便”再包一层旧名。
4. 若某个测试只是验证旧对象行为，要么重写成新对象 contract，要么删除。
5. 所有 PyO3 公开类型修改后，必须以 Rust 真实类型为准更新 stub；不手工补一层 Python 镜像声明。

## 8. 历史验收定义

只有同时满足以下条件，这份历史补充执行计划才算完成：

1. `src`、`py_entry`、`python` 中不再出现 `DataContainer`
2. `src`、`py_entry`、`python` 中不再出现 `BacktestSummary`
3. `src`、`py_entry`、`python` 中不再出现任何 `pack/result -> legacy` 回桥 helper
4. 单次回测、批量回测、优化、敏感性、WF、图表、导出、scanner 全部以 `DataPack / ResultPack` 直连
5. `just check` 通过
6. `just test` 通过

未满足任一条，都只能算“主链已新、全仓未清”，不能算当时计划中的最终完成。

当前回看：

1. 上述历史收口目标已在 `04_review` 中记录为完成。
2. 当前仓库现状不再以本文描述为准，而以源码与 review 结果为准。
