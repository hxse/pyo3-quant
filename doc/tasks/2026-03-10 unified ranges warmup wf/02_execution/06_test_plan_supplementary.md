# 统一 Ranges / Warmup / WF 测试补充文档

对应主文：

1. [02_test_plan.md](./02_test_plan.md)

本页只保留不参与阶段 gate 的补充内容：

1. 当前测试现状
2. 推荐保留的 PyO3 测试工具函数
3. 测试数据策略
4. 建议新增测试文件清单
5. 建议执行顺序
6. AI 审阅清单

## 1. 当前测试现状总结

从现有测试看，项目已经形成了三条比较好的习惯：

1. 偏 contract test / regression guard，而不是大而全黑盒乱跑。
2. 通过 `py_entry/Test/shared/backtest_builders.py` 复用共享构造器，避免大段测试样板代码。
3. WF 测试已经有性能意识，但后续新方案仍然要进一步压小默认数据量与优化轮次。

当前现有测试里，最值得继续复用的风格是：

1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
3. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
4. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
5. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

## 2. 推荐保留的 PyO3 测试工具函数

为了让测试文档和测试代码都更好写，建议保留少量稳定、可测试、不会污染主工作流的 PyO3 工具函数。

推荐保留：

1. `build_mapping_frame(...)`
2. `build_data_pack(...)`
3. `build_result_pack(...)`
4. `slice_data_pack_by_base_window(...)`
5. `extract_active(...)`

保留理由：

1. 它们本身就是正式真值入口或高风险切片入口。
2. 用它们可以直接写小样本 contract test，不必每次都跑完整 WF。
3. 这些函数的输入输出稳定、契约清楚，适合长期保留。
4. 其中 `build_mapping_frame(...)` 需要特别区分：
   - 在生产链路里仍只由 `build_data_pack(...)` 调用
   - 但对测试 / 调试层允许保留 PyO3 暴露，不视为第二套业务入口

不建议为了测试而暴露的函数：

1. 只服务单个临时实现细节的内部 helper
2. 会诱导调用方绕开主工作流的半成品构造函数
3. 没有稳定输入输出、后续很可能继续改名或改语义的内部状态函数

## 3. 建议测试数据策略

优先级：

1. 先用小样本、无 gaps、固定 seed 的合成数据
2. 再用少量带交易的场景
3. 最后只保留极少数 stitched / WF 回归用较大样本

建议：

1. 所有 contract test 默认固定 seed
2. 所有工具函数测试优先无 gaps
3. stitched / segmented replay 测试优先选择“有边界、但样本不大”的场景

## 4. 建议新增测试文件清单

建议新增：

1. `py_entry/Test/backtest/test_data_pack_contract.py`
2. `py_entry/Test/backtest/test_result_pack_contract.py`
3. `py_entry/Test/backtest/test_strip_indicator_time_columns_contract.py`
4. `py_entry/Test/backtest/test_mapping_projection_contract.py`
5. `py_entry/Test/backtest/test_performance_contract.py`
6. `py_entry/Test/backtest/test_extract_active_contract.py`
7. `py_entry/Test/walk_forward/test_window_slice_contract.py`
8. `py_entry/Test/walk_forward/test_stitched_contract.py`
9. `src/backtest_engine/walk_forward/plan.rs`
10. `src/backtest_engine/walk_forward/time_ranges.rs`
11. `src/backtest_engine/walk_forward/next_window_hint.rs`
12. `src/backtest_engine/backtester/tests.rs`

继续沿用并扩展：

1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
3. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
4. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
5. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

## 5. 建议执行顺序

建议按这个顺序补测试：

1. 先补 builder / mapping / `SourceRange` 不变量测试
2. 再补 `extract_active(...)`
3. 再补窗口索引与窗口切片
4. 再补跨窗注入
5. 再补 stitched / segmented replay
6. 最后才补完整 WF 回归

## 6. 建议 AI 审阅清单

执行测试前，先用 AI 审一遍是否踩到下面问题：

1. 是否过度依赖完整 `Backtest.walk_forward(...)` 黑盒入口
2. 是否遗漏了 PyO3 工具函数级 contract test
3. 是否出现大样本、过多优化轮次的慢测试
4. 是否把摘要文档里的强不变量漏成了弱断言
5. 是否在 stitched 测试里直接比较了不该直接比较的原始 `mapping` 整数值
6. stitched 测试是否已经按 `run_backtest_with_schedule(...)` 与 `backtest_schedule` 重基契约组织，而不是绕开正式 replay 真值链
