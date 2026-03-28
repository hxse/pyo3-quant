# WF 最小改动方案 - 测试执行文档

## 1. 目标与决策
本文件只描述测试落地，不解释架构动机。

本次测试策略采用：
1. 三阶段顺序：先指标契约，再 WF 内部容器与执行链，最后 mapping 覆盖补拉。
2. Fail-Fast：所有不满足契约的场景必须直接报错。
3. 接口一致性：涉及 PyO3 接口变更必须先 `just stub`。
4. WF 重型断言统一复用单个轻量场景，避免构建多份大样本 WF。
5. 新增 `strategy_hub` 入口专项与架构约束专项，防止回退到旧目录结构。

---

## 2. 保留项（继续运行）
以下测试文件保留并继续运行：
1. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

保留原因：
1. 它覆盖 stitched 资金连续性、窗口顺序、时间严格递增、可复现性等底线行为。
2. 新方案仍要求这些行为保持不变。

---

## 3. 测试文件与范围

### 3.1 指标契约专项（Phase 1）
文件：
1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`

覆盖点：
1. 每个指标都实现：
   - `required_warmup_bars(resolved_params)`
   - `warmup_mode()`
2. `required_warmup_bars` 等于该指标全部输出列前导空值最大值。
3. `Strict/Relaxed` 运行时校验口径正确。
4. `resolve_indicator_contracts(...)` 的 source 聚合结果正确。
5. `indicator_warmup_bars_base` 只绑定 `base_data_key`。
6. 契约非法、参数非法直接报错。

### 3.2 预检入口专项（Phase 1 -> Phase 2）
文件：
1. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`

覆盖点：
1. `Backtest.validate_wf_indicator_readiness(...)` 成功路径。
2. 失败路径直接抛异常。
3. `NoWarmup` 失败路径仍必须 Fail-Fast。
4. 无指标策略预检通过，且 base warmup 为 `0`。
5. 错误信息包含实例名、source、required warmup、observed 值。

### 3.3 strategy_hub 入口专项（Phase 2）
文件：
1. `py_entry/Test/strategy_hub/test_strategy_hub_precheck_entrypoints.py`

覆盖点：
1. `executor` 入口显式预检一次。
2. `strategy_searcher` 在 `walk_forward` 模式下显式预检一次。
3. 失败短路：预检失败不进入后续执行。
4. WF 配置透传正确：
   - `train_bars`
   - `min_warmup_bars`
   - `test_bars`
   - `inherit_prior`
   - `optimizer_config`
   - `wf_warmup_mode`

### 3.4 WF 容器与切片专项（Phase 2）
文件：
1. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
2. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

覆盖点：
1. 跨窗判定来源正确：
   - 仅使用“上一窗口 `Test` 末根”持仓状态
2. 注入顺序正确：
   - `Test` 倒数第二根注入双向离场
   - `BorrowFromTrain/ExtendTest` 在 `TestWarmup` 最后一根注入同向开仓
   - `NoWarmup` 在 `Test` 第一根注入同向开仓
3. 第一窗规则正确：
   - 第一窗不做跨窗开仓
   - 第一窗仍执行测试段离场注入
4. 窗口级切片口径正确：
   - `indicators` 走 source 语义
   - `signals/backtest` 走 base 语义
5. 窗口级资金列不重建。
6. stitched 阶段重建资金列后再算绩效。
7. stitched 时间序列严格递增且与理论时间列一致。
8. 同配置重复执行结果一致。

### 3.5 mapping 覆盖与数据质量专项（Phase 3）
文件：
1. `py_entry/Test/data_generator/test_mapping_coverage_guards.py`

覆盖点：
1. 正常覆盖场景成功。
2. 首端不覆盖直接报错。
3. 尾端不覆盖直接报错。
4. 原始 source 含 `NaN/null` 直接报错。
5. start/end 补拉循环可收敛。
6. 超过补拉上限直接报错。
7. `end_backfill_min_step_bars` 生效。
8. `base_data_key` 必须是最小周期。

### 3.6 架构约束专项（防回退）
文件：
1. `py_entry/Test/strategy_hub/test_architecture_guards.py`
2. `py_entry/Test/strategy_hub/test_strategy_name_guard.py`
3. `py_entry/Test/strategy_hub/test_registry_loader.py`

覆盖点：
1. 旧目录与旧入口不再被新代码依赖。
2. strategy hub 目录结构与入口约束不回退。
3. 策略名唯一性约束有效。
4. 注册器加载契约有效。

---

## 4. 关键断言口径
1. 预检逻辑唯一实现位于 Rust，Python 只封装调用。
2. `NoWarmup` 只关闭预热扩展，不关闭 Fail-Fast。
3. source 区间只能来自 `build_source_ranges(...)`。
4. `WFDataContainer/WFSummaryContainer` 只能在 WF 内部使用。
5. 回测引擎与优化器只消费通用容器载荷。
6. `window_test_results` 只保留测试非预热区。
7. stitched 结果必须来自窗口结果拼接，不允许回全量数据二次切片重建。
8. `time` 列校验必须严格到长度、顺序、逐行值完全一致。
9. WF 重型用例统一复用单场景，避免高开销重复构建。

---

## 5. 执行顺序与命令
严格串行执行，先检查再测试。

1. 类型与语法检查：
```bash
just stub
just check
```

2. 指标契约专项：
```bash
just test-py path="py_entry/Test/indicators/test_indicator_warmup_contract.py"
just test-py path="py_entry/Test/indicators/test_resolve_indicator_contracts.py"
```

3. 预检入口专项：
```bash
just test-py path="py_entry/Test/walk_forward/test_wf_precheck_contract.py"
```

4. strategy_hub 入口专项：
```bash
just test-py path="py_entry/Test/strategy_hub/test_strategy_hub_precheck_entrypoints.py"
```

5. WF 容器与切片专项：
```bash
just test-py path="py_entry/Test/walk_forward/test_wf_signal_injection_contract.py"
just test-py path="py_entry/Test/walk_forward/test_walk_forward_guards.py"
```

6. mapping 覆盖与数据质量专项：
```bash
just test-py path="py_entry/Test/data_generator/test_mapping_coverage_guards.py"
```

7. 架构约束专项：
```bash
just test-py path="py_entry/Test/strategy_hub/test_architecture_guards.py"
just test-py path="py_entry/Test/strategy_hub/test_strategy_name_guard.py"
just test-py path="py_entry/Test/strategy_hub/test_registry_loader.py"
```

8. 全量 Python 测试：
```bash
just test-py
```

9. 全量测试：
```bash
just test
```

---

## 6. 验收标准
1. `just check` 通过。
2. 指标契约专项通过。
3. 预检入口专项通过。
4. strategy_hub 入口专项通过。
5. WF 容器与切片专项通过。
6. mapping 覆盖与数据质量专项通过。
7. 架构约束专项通过。
8. 全量 `just test` 通过。
9. 无新增 flaky 行为。

---

## 7. 历史执行回填（2026-03-01）
以下结果保留原执行记录，仅作为历史回填，不代表本次文档更新重新执行：
1. `just check`：通过
2. `just test-py`：通过（历史记录：`482 passed, 45 skipped`）
3. `just test`：通过
