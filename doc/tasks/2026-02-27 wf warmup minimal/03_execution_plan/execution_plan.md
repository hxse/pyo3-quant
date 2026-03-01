# WF 最小改动方案 - 可执行总计划

## 1. 目标
本计划只定义执行顺序、改动范围、验收闸门，不解释方案动机。

统一目标：
1. 先落地指标回调契约与聚合函数。
2. 再接入 WF 预检与工作流入口。
3. 最后落地 Python 网络层覆盖补拉与 mapping 回归。

全局硬约束：
1. 错误体系必须复用 `src/error`（`QuantError`/`BacktestError` 及其 PyO3 映射），禁止新增平行错误系统。
2. 涉及 PyO3 接口新增或签名变更时，必须执行 `just stub` 并更新 `python/pyo3_quant/**/*.pyi`。

---

## 2. 阶段闸门（必须串行）
1. Phase 1 未通过：禁止进入 Phase 2。
2. Phase 2 未通过：禁止进入 Phase 3。
3. 任一阶段失败：直接停止，不做临时兼容。

---

## 3. Phase 1（指标规范化，第一闸门）

### 3.1 改动范围
1. 扩展 `Indicator` trait，所有已注册指标必须实现：
- `required_warmup_bars(resolved_params) -> usize`
- `warmup_mode() -> WarmupMode`（`Strict | Relaxed`）
2. 落地契约聚合函数并导出 PyO3：
- `resolve_indicator_contracts(indicators_params_py) -> IndicatorContractReport`
3. 预检错误与契约错误统一落在现有错误体系（优先 `BacktestError::ValidationError` / `DataValidationError`）。
4. 明确不在指标 DataFrame 中新增掩码列，契约信息只走独立结构。
5. 预热口径固定为“全列口径”：
- `required_warmup_bars` 按该指标全部输出列前导空值最大值定义；
- 运行时 `Strict/Relaxed` 校验也按该指标全部输出列执行。

### 3.2 涉及文件（核心）
1. `src/backtest_engine/indicators/**/*.rs`
2. `src/backtest_engine/indicators/registry.rs`
3. `src/backtest_engine/indicators/py_bindings.rs`（或同等导出位置）
4. `src/lib.rs`（如需注册新 PyO3 接口）
5. `src/error/quant_error.rs`
6. `src/error/py_interface.rs`
7. `src/error/mod.rs`（如需新增错误码映射）
8. `py_entry/runner/backtest.py`（封装 `validate_wf_indicator_readiness(...)` 调用）
9. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
10. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`

### 3.3 验收
1. `just stub` 通过并生成最新 `.pyi`。
2. `just check` 通过。
3. 指标契约专项测试通过（见测试执行文档）。
4. `resolve_indicator_contracts` 可从 Python 调用并返回可诊断结果。

---

## 4. Phase 2（WF 接入与工作流贯通）

### 4.1 改动范围
1. `Backtest.validate_wf_indicator_readiness(...)` 落地并作为唯一预检入口。
2. private 三入口显式预检一次：
- pipeline；
- searcher 的 walk_forward 分支；
- `demo.ipynb` 手动分阶段入口。
3. 参数链路打通：
- 新增/透传 `wf_warmup_mode`；
- `wf_warmup_mode` 必须落为 Rust enum 并通过 PyO3 暴露（禁止 Python 字符串直传）；
- 移除 `wf_allow_internal_nan_indicators`。
4. 跨窗注入切换为“上一窗口 Test 末根判定”：
- 跨窗判定只看上一窗口 `Test` 末根持仓（`entry_*_price`/`exit_*_price`）；
- 禁止再用“当前窗口 `Transition + Test` 首跑回测结果”判定跨窗。
5. 注入执行链固定为：
- 先跑 `Signals`；
- 注入信号；
- 再跑 `run_backtest -> analyze_performance`。
6. 资金列口径保持不变：
- 窗口级 `Test` 回测结果不做资金列重建；
- 仅在 `stitched` 汇总阶段按窗口边界重建资金列。
7. 第一窗注入规则固定：
- 第一窗只做 `Test` 倒数第二根双向离场注入；
- 第一窗不做跨窗开仓注入。
8. 禁止旧注入逻辑：
- 禁止在 `Transition` 倒数第二根再注入离场；
- 禁止“过渡期开仓后再判定跨窗”。
9. 保持回测主链与容器体系不变。
10. 评估区间（`test_with_warmup = Transition + Test`）切片范围按模式固定：
- BorrowFromTrain：`evaluation_range_i = [base_start_i + T - E, base_start_i + T + S)`；
- ExtendTest / NoWarmup：`evaluation_range_i = [base_start_i + T, base_start_i + T + E + S)`；
- 统一等价表达：`evaluation_range_i = [Transition_i.start, Test_i.end)`。
11. runner 必须维护跨窗状态变量（如 `prev_test_last_position`）：
- 首窗默认“无上一窗持仓”；
- 每窗结束后用 `Test_i` 末根结果更新状态；
- 下一窗只消费该状态决定是否在 `Transition_i` 末根注入开仓。
12. `effective_transition_bars >= 1` 在新注入口径下已充分，不再需要 `>= 2`。
13. BorrowFromTrain 额外运行时校验：`E <= T`，不满足直接报错（Fail-Fast）。

### 4.2 涉及文件（核心）
1. `py_entry/runner/backtest.py`
2. `py_entry/private_strategies/config.py`
3. `py_entry/private_strategies/template.py`
4. `py_entry/private_strategies/strategy_searcher.py`
5. `py_entry/private_strategies/demo.ipynb`
6. `src/types/inputs/walk_forward.rs`（新增 `wf_warmup_mode` 到 PyO3 类型）
7. `src/backtest_engine/walk_forward/data_splitter.rs`（按模式生成窗口区间）
8. `src/backtest_engine/walk_forward/runner.rs`（跨窗判定来源与注入顺序重写）
9. `src/backtest_engine/walk_forward/mod.rs`（如需新增/调整导出）
10. `py_entry/Test/backtest/test_wf_precheck_contract.py`（Phase 2 预检集成）

### 4.3 验收
1. 若改动了 PyO3 类型或接口，`just stub` 与 `.pyi` 一致性通过。
2. pipeline/searcher/ipynb 三入口都能“显式预检一次”后正常执行。
3. `walk_forward` 路径稳定 Fail-Fast。
4. 跨窗注入判定来源已切换为“上一窗口 Test 末根”，不存在“过渡期开仓污染判定”。
5. 第一窗仅执行测试段离场注入，不注入跨窗开仓。
6. 不再出现 `transition_exit` 注入点。
7. `test_wf_signal_injection_contract.py` 与 `test_walk_forward_guards.py` 均通过。
8. `E == 1` 边界测试通过，注入逻辑仍正确。
9. BorrowFromTrain 的 `E > T` 拒绝路径测试通过。
10. 现有单次回测、优化、敏感性流程不退化。

---

## 5. Phase 3（Python 覆盖补拉 + mapping 回归）

### 5.1 改动范围
1. 在 `generate_data_dict` 内部实现覆盖补拉：
- start 侧：前移 `since` 直到覆盖；
- end 侧：增大 `limit` 直到覆盖；
- end 侧最小补拉参数：`end_backfill_min_step_bars`，默认 `5`。
2. 不改变对外请求协议（仍是 `since + limit`）。
3. 覆盖最终判定仍以 Rust `build_time_mapping` 为准（Fail-Fast）。
4. `build_time_mapping` 增加并执行 `base_data_key` 最小周期约束校验，失败直接报错：
- 统一走 `data_key -> interval_ms` 解析工具函数；
- 不允许字符串字典序比较；
- 解析失败直接 Fail-Fast。

### 5.2 涉及文件（核心）
1. `py_entry/data_generator/data_generator.py`
2. `py_entry/data_generator/config.py`（若需要放置内部参数配置）
3. `py_entry/private_strategies/config.py`（如需透传到数据层配置）
4. `src/backtest_engine/data_ops/mod.rs`（仅在 mapping 校验信息需补充时）

### 5.3 验收
1. mapping 覆盖与数据质量测试通过。
2. 覆盖失败时错误码与报错路径可诊断。
3. WF 测试默认采用轻量参数：`kline_bars <= 2000`、`optimizer_rounds <= 30`。
4. 若测试耗时偏高，优先降低优化次数，不放大 K 线数量。
5. 在上述轻量参数下，WF 冒烟稳定通过。

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
3. 文档、实现、测试三者口径一致。

---

## 8. 执行结果回填（2026-03-01）
执行时间：`2026-03-01 16:19:51 CST`

### 8.1 参数透传落地检查（private 公共配置）
本 task 新增并要求透传到 private 公共配置的参数如下：
1. `wf_warmup_mode`（WF 预热模式，Rust enum，经 PyO3 暴露）
2. `end_backfill_min_step_bars`（Python 数据请求层 end 侧最小补拉步长）

落地点：
1. `py_entry/private_strategies/config.py`（`DEFAULT_WF_CONFIG`、`DEFAULT_FETCH_CONFIG`、构建函数透传）
2. `py_entry/runner/pipeline.py`（summary 输出 `effective_transition_bars` / `wf_warmup_mode`）

### 8.2 最终门禁执行结果
1. `just check`：通过
2. `just test-py`：通过（`482 passed, 45 skipped`）
3. `just test`：最终通过（`482 passed, 45 skipped`，Rust tests/doc-tests 全通过）

### 8.3 过程修复记录（一次）
1. 首次执行 `just test` 时出现 1 个失败：
   - `py_entry/Test/data_generator/test_generate_data_dict_integration.py::TestGenerateDataDictIntegration::test_generate_data_dict_with_ha_renko`
   - 原因：用“短样本必然触发 Renko 行数不足报错”的断言存在随机路径波动，导致偶发失败。
2. 修复方式：
   - 将该用例改为确定性正向集成断言（提高样本长度并校验 `ha_15m` / `renko_1h` 产物存在与最小行数）。
3. 修复后复跑 `just test`：全绿。
