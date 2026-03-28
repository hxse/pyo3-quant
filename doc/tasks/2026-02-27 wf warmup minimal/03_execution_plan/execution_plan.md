# WF 最小改动方案 - 可执行总计划

## 1. 目标
本计划只定义执行顺序、改动范围与验收闸门，不解释方案动机。

统一目标：
1. 先落地指标契约与预检聚合。
2. 再落地 WF 内部容器、base/source 切片与执行链。
3. 最后落地 Python 数据覆盖补拉与 mapping 回归。

全局硬约束：
1. 错误体系必须复用 `src/error`，禁止新增平行错误系统。
2. 涉及 PyO3 接口/类型变更，必须执行 `just stub`。
3. WF 内部统一使用 `WFDataContainer/WFSummaryContainer`，禁止直接切片裸 `DataContainer/BacktestSummary`。
4. 回测引擎与优化器只消费通用容器载荷。

---

## 2. 阶段闸门（必须串行）
1. Phase 1 未通过：禁止进入 Phase 2。
2. Phase 2 未通过：禁止进入 Phase 3。
3. 任一阶段失败：直接停止，不做兼容层。

---

## 3. Phase 1（指标契约与预检聚合）

### 3.1 改动范围
1. 扩展指标契约：
   - `required_warmup_bars(resolved_params) -> usize`
   - `warmup_mode() -> Strict | Relaxed`
2. 落地聚合函数并导出 PyO3：
   - `resolve_indicator_contracts(...) -> IndicatorContractReport`
3. 统一全列口径：
   - `required_warmup_bars` 按全部输出列前导空值最大值定义
   - `Strict/Relaxed` 校验也按全部输出列执行
4. Python 侧统一封装：
   - `Backtest.validate_wf_indicator_readiness(...)`
5. 失败直接报错，不返回软状态。

### 3.2 涉及文件（核心）
1. `src/backtest_engine/indicators/**/*.rs`
2. `src/backtest_engine/indicators/registry.rs`
3. `src/types/outputs/indicator_contract.rs`
4. `src/lib.rs`（如需注册新 PyO3 接口）
5. `src/error/**/*.rs`
6. `py_entry/runner/backtest.py`
7. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
8. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
9. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`

### 3.3 验收
1. `just stub` 通过并生成最新 `.pyi`。
2. `just check` 通过。
3. 指标契约专项测试通过。
4. `resolve_indicator_contracts` 与 `validate_wf_indicator_readiness` 可从 Python 正常调用。

---

## 4. Phase 2（WF 容器、切片与执行链）

### 4.1 改动范围
1. base 窗口生成按三模式统一：
   - `BorrowFromTrain`
   - `ExtendTest`
   - `NoWarmup`
2. source 区间统一由 `build_source_ranges(...)` 产出。
3. 引入 WF 内部专用容器：
   - `WFDataContainer`
   - `WFSummaryContainer`
4. 落地两个内部切片工具：
   - `slice_wf_data(...)`
   - `slice_wf_summary(...)`
5. WF 固定执行顺序：
   - 预检
   - base 窗口生成
   - source 映射
   - 训练容器/评估容器切片
   - 第一遍执行到 `Signals`
   - 注入信号
   - 第二遍执行 `Backtest`
   - 切到测试非预热区
   - 计算窗口级 `Performance`
   - stitched 拼接
   - 重建 stitched 资金列
   - 重算 stitched `Performance`
   - 对外脱壳
6. 跨窗状态判定固定为“上一窗口 `Test` 末根”。
7. 第一窗只做测试段离场注入，不做跨窗开仓注入。
8. 窗口级不重建资金列；只在 stitched 阶段重建。
9. `indicators` 保持 source 语义，`signals/backtest/performance` 保持 base 语义。
10. stitched 后必须执行时间一致性强校验。

### 4.2 涉及文件（核心）
1. `src/types/inputs/walk_forward.rs`
2. `src/types/outputs/walk_forward.rs`
3. `src/backtest_engine/walk_forward/data_splitter.rs`
4. `src/backtest_engine/walk_forward/runner.rs`
5. `src/backtest_engine/walk_forward/mod.rs`
6. `py_entry/runner/backtest.py`
7. `py_entry/strategy_hub/core/config.py`
8. `py_entry/strategy_hub/core/executor.py`
9. `py_entry/strategy_hub/core/strategy_searcher.py`
10. `py_entry/strategy_hub/demo.ipynb`
11. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
12. `py_entry/Test/walk_forward/test_walk_forward_guards.py`
13. `py_entry/Test/strategy_hub/test_strategy_hub_precheck_entrypoints.py`

### 4.3 验收
1. 若改动了 PyO3 类型或接口，`just stub` 与 `.pyi` 一致性通过。
2. `executor/searcher/demo.ipynb` 三入口都能显式预检一次后正常执行。
3. `walk_forward` 路径稳定 Fail-Fast。
4. source 区间只来自 `build_source_ranges(...)`，不存在二次推导。
5. 第一窗仅执行测试段离场注入，不注入跨窗开仓。
6. 窗口级资金列不重建，stitched 阶段资金列重建后再算绩效。
7. `test_wf_signal_injection_contract.py` 与 `test_walk_forward_guards.py` 通过。
8. 现有单次回测、优化、敏感性流程不退化。

---

## 5. Phase 3（数据覆盖补拉与 mapping 回归）

### 5.1 改动范围
1. 在 `generate_data_dict` 内部实现覆盖补拉：
   - start 侧：前移 `since`
   - end 侧：增大 `limit`
2. end 侧最小补拉参数：
   - `end_backfill_min_step_bars`
3. 不改变对外请求协议，仍是 `since + limit`。
4. 覆盖最终判定仍以 Rust `build_time_mapping` 为准。
5. `base_data_key` 最小周期约束仍由 Rust 侧直接校验。

### 5.2 涉及文件（核心）
1. `py_entry/data_generator/data_generator.py`
2. `py_entry/data_generator/config.py`
3. `py_entry/strategy_hub/core/config.py`
4. `src/backtest_engine/data_ops/mod.rs`
5. `py_entry/Test/data_generator/test_mapping_coverage_guards.py`

### 5.3 验收
1. mapping 覆盖与数据质量测试通过。
2. 覆盖失败时错误码与报错路径可诊断。
3. WF 测试默认保持轻量参数。
4. 若测试耗时偏高，优先降低优化次数，不放大 K 线数量。

---

## 6. 统一命令顺序
1. `just stub`（仅在本阶段有 PyO3 接口/类型改动时必跑）
2. `just check`
3. 按阶段执行对应 pytest（见 `testing_execution_plan.md`）
4. `just test-py`
5. `just test`

---

## 7. 完成定义
1. 三阶段全部通过，且闸门顺序无跳步。
2. `just test` 全绿。
3. 摘要文档、架构文档、执行文档、实现与测试口径一致。

---

## 8. 历史执行回填（2026-03-01）
以下结果保留原执行记录，仅作为历史回填，不代表本次文档更新重新执行：
1. `just check`：通过
2. `just test-py`：通过（历史记录：`482 passed, 45 skipped`）
3. `just test`：通过（Rust + Python 全绿）
