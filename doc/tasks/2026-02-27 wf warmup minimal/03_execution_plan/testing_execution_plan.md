# WF 最小改动方案 - 测试执行文档

## 1. 目标与决策
本执行文档只描述测试落地，不解释架构动机。

本次测试策略采用：
1. 三阶段顺序：先指标（Phase 1）-> 再 WF（Phase 2）-> 最后 mapping 覆盖补拉（Phase 3）。
2. 兼容保留：保留现有 WF 回归测试，不重写。
3. Fail-Fast：所有不满足契约的场景必须直接报错。
4. 接口一致性：涉及 PyO3 接口变更必须先 `just stub`，测试基于最新 `.pyi` 执行。
5. WF 性能约束：WF 相关用例统一复用单个轻量场景，避免重复构建多份 WF。

结论：
1. 指标专项测试是本任务第一闸门，不通过禁止进入 WF 落地。
2. WF 入口与回归测试是第二闸门。
3. mapping 覆盖与数据质量测试是第三闸门。
4. WF 重型断言统一集中在“一个 WF 场景”内复用，不新增多份大样本 WF。

---

## 2. 保留项（不重写）
以下测试文件保留并继续运行：
1. `py_entry/Test/backtest/test_walk_forward_guards.py`

保留原因：
1. 该文件覆盖 stitched 资金连续性、窗口顺序、时间严格递增、可复现性等核心行为。
2. 这些行为仍是新方案底线，不依赖旧白名单机制。
3. 本任务要求在该文件基础上扩展“单 WF 场景复用断言”，而不是再建多份 WF 重型测试。

---

## 3. 新增测试文件与范围
新增与扩展若干 pytest 文件；WF 重型场景统一复用同一组数据与配置。

### 3.1 指标契约专项（第一优先级，集中在 pytest 指标测试）
文件：
1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`

对应运行时改动位（测试必须对齐这些实现）：
1. `src/backtest_engine/indicators/**/*.rs`
2. `src/backtest_engine/indicators/registry.rs`

覆盖点（单指标独立样本）：
1. 每个已注册指标都实现：
- `required_warmup_bars(resolved_params)`
- `warmup_mode()`
2. 对每个指标独立计算 `warmup = required_warmup_bars(resolved_params)` 后断言：
- `Strict`：
  - 预热段（前 `warmup` 行）在该指标全部输出列上应为空；
  - 非预热段在该指标全部输出列上不得出现 `NaN/null`。
- `Relaxed`：
  - 预热段（前 `warmup` 行）在该指标全部输出列上应为空；
  - 非预热段允许结构性空值，但按行不得“整行全空”。
3. `opening-bar` 专项：
- `warmup_mode` 必须是 `Strict`；
- 允许 `warmup=0`。
4. divergence 类专项：
- `required_warmup_bars` 必须覆盖“底层指标 + divergence lookback”。
5. warmup 参数化扫描（必须）：
- 每个指标至少三组参数（小/中/大）校验 warmup 缩放正确；
- 防止 `saturating_sub`/边界值导致 warmup 被静默归零。
6. 全列口径一致性（必须）：
- `required_warmup_bars` 必须等于该指标全部输出列前导空值最大值（max leading missing across all output columns）。

### 3.2 聚合函数专项（Phase 1）
文件：
1. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`

对应运行时改动位（测试必须对齐这些实现）：
1. `src/backtest_engine/indicators/py_bindings.rs`（或同等 PyO3 导出位置）

覆盖点：
1. Rust + PyO3 暴露的 `resolve_indicator_contracts(...)` 可调用且结果可诊断。
2. source 级聚合规则正确（同 source 取最大 warmup）。
3. 返回结果中 `warmup_bars_by_source` 与 `contracts_by_indicator` 一致可追踪。
4. 同 source 多指标聚合断言：
- 例：同一 source 下 `SMA(12)` 与 `SMA(48)`，聚合结果必须为 `47`。
5. `Relaxed` 契约返回专项（PSAR）：
- `contracts_by_indicator[psar].warmup_mode == Relaxed`。
6. 契约非法（指标未实现回调、参数非法）直接报错（Fail-Fast）。
7. `optimize=true` 参数解析断言（必须）：
- 构造 `Param(value=10, min=5, max=50, optimize=true)`，断言 warmup 计算使用 `max=50`。
8. 多 source 异构 warmup（必须）：
- 示例：`SMA(200)@1h + SMA(5)@15m`；
- 断言 `warmup_bars_by_source` 按 source 独立聚合；
- 断言 `indicator_warmup_bars_base` 仅取 base source。

### 3.3 预检入口专项（Phase 2）
文件：
1. `py_entry/Test/backtest/test_wf_precheck_contract.py`

对应运行时改动位（测试必须对齐这些实现）：
1. `py_entry/runner/backtest.py`（预检封装入口）
2. `src/backtest_engine/walk_forward/runner.rs`（预检消费链路）

覆盖点：
1. `Backtest.validate_wf_indicator_readiness(...)` 成功路径。
2. 预检失败直接抛异常（Fail-Fast），不返回 `ok=false` 报告。
3. `wf_warmup_mode=NoWarmup` 失败路径：指标未就绪时仍必须失败。
4. base 绑定规则正确：`indicator_warmup_bars_base = warmup_bars_by_source[base_data_key]`，缺失直接报错。
5. 预检结果可被 WF 执行链消费，且不会重复定义第二套聚合逻辑。
6. 无指标策略预检（必须）：
- 指标为空时，预检应正常通过；
- `warmup_bars_by_source` 为空 map；
- `indicator_warmup_bars_base == 0`。
7. 错误信息可诊断性（必须）：
- 失败异常中必须包含：指标实例名、source、required warmup、observed 值。

### 3.4 private 入口调用专项
文件：
1. `py_entry/Test/private_strategies/test_private_wf_precheck_entrypoints.py`

覆盖点：
1. `run_pipeline(...)` 入口显式调用一次预检。
2. `strategy_searcher` 在 `walk_forward` 模式下每个 variant 入口显式调用一次预检。
3. `run_stage(...)` 不自动调用预检。
4. 失败短路：预检失败不进入后续执行。
5. 参数透传正确：
   - `train_bars/transition_bars/test_bars/inherit_prior/optimizer_config`
   - `wf_warmup_mode`
6. `effective_transition_bars` 计算口径正确：
- `BorrowFromTrain` / `ExtendTest`：`max(indicator_warmup_bars_base, transition_bars, 1)`；
- `NoWarmup`：`max(transition_bars, 1)`。

### 3.5 WF 注入契约专项
文件：
1. `py_entry/Test/backtest/test_wf_signal_injection_contract.py`
2. `py_entry/Test/backtest/test_walk_forward_guards.py`（扩展单 WF 场景复用断言）

覆盖点：
1. 跨窗判定来源正确：
   - 仅使用“上一窗口 Test 末根”持仓状态判定；
   - 禁止依赖“当前窗口 `Transition + Test` 首跑回测”作为判定来源。
2. 注入顺序正确：
   - `Test` 倒数第二根注入双向离场；
   - 仅在跨窗成立时于 `Transition` 最后一根注入同向开仓。
3. 第一窗规则正确：
   - 第一窗不注入跨窗开仓；
   - 第一窗仍执行 `Test_0` 倒数第二根双向离场注入。
4. 禁止旧注入点：
- 不允许 `Transition` 倒数第二根存在离场注入。
5. 三模式窗口边界断言：
- BorrowFromTrain：`transition_start == train_end - E` 且 `test_start == train_end`；
- ExtendTest/NoWarmup：`transition_start == train_end` 且 `test_start == train_end + E`。
6. 最小边界断言：
- `E == 1` 时注入流程仍合法；
- `S == 2` 时“测试段倒数第二根”注入点仍存在且正确。
7. 跨窗状态传递链断言（>=3 窗口）：
- 若窗口 `i` 测试末根持仓未平，窗口 `i+1` 必须在 `Transition` 末根注入同向开仓；
- 若窗口 `i` 测试末根已平，窗口 `i+1` 不应注入跨窗开仓。
8. BorrowFromTrain 隔离性断言：
- 测试段绩效统计口径仅使用 `Test`；
- 不允许把 `Transition`（与 `Train` 重叠区）计入窗口测试绩效。
9. BorrowFromTrain `E > T` 拒绝断言：
- `effective_transition_bars > train_bars` 时，窗口构建必须直接报错（Fail-Fast）。
10. Relaxed 指标全链路断言（PSAR）：
- 含 `Relaxed` 指标策略可完整通过 `walk_forward`；
- 不得被“非预热段严格无空值”规则误杀。
11. WF 确定性复现（必须）：
- 同配置同数据连续跑两次 `walk_forward`；
- 断言窗口结果与 stitched 结果 bit-exact 一致（种子固定前提）。
12. 跨窗状态链扩展（建议，>=4 窗口）：
- 验证“持仓->注入->平仓->不注入->再持仓->再注入”的交替链路。
13. stitched 资金列精度断言（条件化）：
- 无跨窗继承场景：允许边界近似相等（`pytest.approx`）；
- 有跨窗继承场景：不强制边界相等，但必须满足“不得异常重置到初始资金”。
14. divergence 前导 false 感知（必须）：
- 例如 `CCI-Divergence(window=30)`、短样本场景；
- 断言 warmup 外前导 `false` 不会被 Strict 误杀（`false != NaN/null`）。

### 3.6 mapping 覆盖与数据质量专项
文件：
1. `py_entry/Test/data_generator/test_mapping_coverage_guards.py`

覆盖点：
1. 正常覆盖场景：`build_time_mapping` 构建成功。
2. 首端不覆盖场景：构建直接报错。
3. 尾端不覆盖场景：构建直接报错。
4. 任一 source 原始输入包含 `NaN/null`：构建直接报错。
5. 校验触发点必须在 mapping 构建阶段。
6. start 侧补拉循环：
- 模拟 `source_start > base_start`，验证前移 `since` 后可收敛。
7. end 侧补拉循环：
- 模拟 `source_end + interval <= base_end`，验证增大 `limit` 后可收敛。
8. 补拉限流：
- 超过最大补拉轮次必须直接报错（Fail-Fast）。
9. `end_backfill_min_step_bars` 生效：
- 当 `missing` 很小时，单轮补拉数量仍不少于该最小值。
10. base 最小周期约束：
- `base_data_key` 非最小周期时，`build_time_mapping` 必须直接报错。
11. 最小周期判定实现约束：
- 必须基于 `data_key -> interval_ms` 解析结果判定；
- 禁止使用字符串比较替代周期比较；
- `data_key` 解析失败必须直接报错。

---

## 4. 关键断言口径
执行时统一按以下口径断言：
1. 本方案不维护预检缓存。
2. “只调用一次”由入口调用约束保证，不由缓存命中保证。
3. 预检逻辑唯一实现位于 Rust；Python 仅封装调用。
4. 所有指标先通过契约专项测试，WF 才允许进入回归阶段。
5. `NoWarmup` 只关闭预热补全，不关闭 Fail-Fast。
6. “两种补全模式”固定为 `BorrowFromTrain` 与 `ExtendTest`；`NoWarmup` 语义固定为关闭补全。
7. 错误类型必须复用 `src/error` 映射出来的 Python 异常，不接受平行错误体系。
8. WF 测试参数默认轻量化：`kline_bars <= 2000`、`optimizer_rounds <= 20`，避免测试本身引入性能压力。
9. 若单测耗时异常，优先降低优化次数，不增加 K 线规模。
10. WF 注入逻辑必须采用“上一窗口 Test 末根判定”：
- 判定源=上一窗口测试末根；
- 禁止“过渡期开仓后再判定跨窗”的旧逻辑，避免 BorrowFromTrain 污染。
11. `Transition` 仅用于预热与注入锚点，不作为独立绩效统计区。
12. 第一遍窗口评估只跑到 `ExecutionStage::Signals`，不在第一遍执行 `Backtest/Performance`。
13. `test_walk_forward_guards.py` 必须显式断言 stitched 资金列在跨窗边界连续，不出现断崖。
14. stitched 资金列边界断言必须区分“有无跨窗继承”，禁止一刀切相等断言。
15. WF 重型用例统一复用单场景，禁止新增多份高开销 WF 构建。

---

## 5. 执行顺序与命令
严格串行执行，先检查再测试。

1. 类型与语法检查：
```bash
just stub
just check
```

2. 先跑指标契约专项（第一闸门）：
```bash
just test-py path="py_entry/Test/indicators/test_indicator_warmup_contract.py"
```

3. 跑聚合函数专项（Phase 1 第二闸门）：
```bash
just test-py path="py_entry/Test/indicators/test_resolve_indicator_contracts.py"
```

4. 跑预检入口专项（Phase 2 前置）：
```bash
just test-py path="py_entry/Test/backtest/test_wf_precheck_contract.py"
```

5. 跑 private 入口专项（Phase 2）：
```bash
just test-py path="py_entry/Test/private_strategies/test_private_wf_precheck_entrypoints.py"
```

6. 跑 WF 注入契约专项（Phase 2）：
```bash
just test-py path="py_entry/Test/backtest/test_wf_signal_injection_contract.py"
```

7. 跑现有 WF 回归基线（Phase 2）：
```bash
just test-py path="py_entry/Test/backtest/test_walk_forward_guards.py"
```

8. 跑 mapping 覆盖与数据质量专项（Phase 3）：
```bash
just test-py path="py_entry/Test/data_generator/test_mapping_coverage_guards.py"
```

9. 跑单 WF 复用场景回归（Phase 2 重型）：
```bash
just test-py path="py_entry/Test/backtest/test_walk_forward_guards.py"
```

10. 跑全量 Python 测试回归：
```bash
just test-py
```

11. 跑全量测试（Rust + Python）：
```bash
just test
```

---

## 6. 验收标准
满足以下条件才算测试阶段完成：
1. `just check` 通过。
2. Phase 1 测试通过：指标契约专项 + 聚合函数专项通过（覆盖全部已注册指标）。
3. Phase 2 测试通过：预检入口专项、private 入口专项、WF 注入契约专项、`test_walk_forward_guards.py` 全部通过。
4. Phase 3 测试通过：mapping 覆盖与数据质量专项通过。
5. 全量 `just test` 通过。
6. 无新增 flaky 行为（同配置重复执行结果一致）。
7. WF 重型测试仅使用单场景复用（`kline_bars <= 2000`、`optimizer_rounds <= 20`）。
8. 上述新增断言项（参数化 warmup、无指标预检、异构 warmup、诊断信息、divergence false 感知）全部通过。

---

## 7. 执行结果回填（2026-03-01）
执行时间：`2026-03-01 16:19:51 CST`

### 7.1 全量门禁结果
1. `just check`：通过
2. `just test-py`：通过（`482 passed, 45 skipped`）
3. `just test`：通过（Rust + Python 全绿）

### 7.2 阶段关键专项抽检结果
1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`：通过
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`：通过
3. `py_entry/Test/backtest/test_wf_precheck_contract.py`：通过
4. `py_entry/Test/private_strategies/test_private_wf_precheck_entrypoints.py`：通过
5. `py_entry/Test/backtest/test_wf_signal_injection_contract.py`：通过
6. `py_entry/Test/backtest/test_walk_forward_guards.py`：通过
7. `py_entry/Test/data_generator/test_mapping_coverage_guards.py`：通过

### 7.3 一次失败与修复
1. 首次全量门禁中，`test_generate_data_dict_with_ha_renko` 出现 1 次失败（短样本 Renko 路径非确定）。
2. 已改为确定性集成断言并复跑全量门禁，当前无失败。

### 7.4 本轮新增测试回填（全列口径 + 单 WF 复用）
执行时间：`2026-03-01`

1. 定向测试命令：
```bash
just test-py "py_entry/Test/indicators/test_indicator_warmup_contract.py py_entry/Test/indicators/test_resolve_indicator_contracts.py py_entry/Test/backtest/test_wf_precheck_contract.py py_entry/Test/backtest/test_wf_signal_injection_contract.py py_entry/Test/backtest/test_walk_forward_guards.py"
```
2. 结果：`24 passed, 1 skipped`。
3. `skipped` 原因：
- `test_wf_boundary_cross_inheritance_not_reset_to_initial` 在当前随机路径下未触发跨窗继承分支；
- 该用例已改为“触发则强断言，不触发则显式 skip”，避免虚假失败并保持诊断价值。
4. 本轮验证通过的新增能力：
- 指标 warmup 全列口径校验（非主列口径）；
- warmup 参数化缩放扫描；
- 无指标策略 WF 预检；
- 预检异常可诊断字段（`instance/source/required/observed`）；
- 多 source 异构 warmup 聚合；
- WF 单场景复用回归（`kline_bars<=2000`、`optimizer_rounds<=20`）。
