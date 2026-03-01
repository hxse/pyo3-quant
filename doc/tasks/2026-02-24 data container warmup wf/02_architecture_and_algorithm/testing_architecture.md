# DataContainer + WF 测试架构（定稿）

本文档定义本次重构后的测试分层与验收口径。
主测试体系为 `pytest`，Rust 单测/集成为辅助兜底。

---

## 1. 测试目标

1. 验证单容器契约：`DataContainer + BacktestSummary`。
2. 验证静态指标契约导出：`resolve_indicator_contracts`。
3. 验证 `build_data_container` 构建期校验。
4. 验证 WF 新执行链与 stitched 一致性。
5. 验证 PyO3 接口与 Python 编排一致。
6. 验证阶段闸门：先过指标契约（A0），再进入容器/WF 主链。

---

## 2. 测试分层

### 2.1 L1 Rust 单元测试（纯函数）

覆盖：
1. `resolve_indicator_contracts`：
   - 参数取值规则（optimize max/value）
   - 同 source 聚合取最大值
   - `indicator_contracts -> required_warmup_dict` 一致性
2. `build_data_container` 内部校验函数：
   - 非预热覆盖通过/失败
   - 映射 non-null 通过/失败
   - source 全区间 `null/NaN` 失败
3. 切片与拼接辅助函数：
   - `run_ranges` 重建相对索引正确
   - 成对切片一致

### 2.2 L2 Rust 集成测试（模块链路）

覆盖：
1. `build_data_container -> run_single_backtest` 主链。
2. `ExecutionStage` 行为一致性（沿用现有枚举）。
3. 绩效仅统计 `data_range`。
4. `has_leading_nan` 退出业务逻辑后的行为回归。

### 2.3 L3 PyO3 契约测试（边界）

覆盖：
1. Py 端可调用 `resolve_indicator_contracts`。
2. Py 端可调用构建/切片/拼接接口。
3. 输入输出类型与 `.pyi` 一致。
4. 错误映射可诊断（Fail-Fast）。

### 2.4 L4 Python 端到端测试（主验收）

覆盖：
1. 单次回测。
2. 优化与参数抖动。
3. WF 全流程：窗口 + 注入 + 回测 + 绩效 + 拼接。
4. 画图成对切片路径。

### 2.5 L5 性能冒烟

固定基线：
1. WF 数据规模：`2000` bars。
2. 优化次数：`30`。
3. 目标：完整 pytest 可稳定跑通。
4. 性能门槛（本地开发机，release 模式）：
   - 单次 WF 端到端用例耗时 `<= 120s`
   - 峰值内存 `<= 2GB`
5. 若超阈值直接失败，视为性能回归。

---

## 3. 关键用例矩阵

### 3.1 指标契约专项（新增重点）

1. `resolve_indicator_contracts` 返回结构校验：
   - `required_warmup_dict`
   - `indicator_contracts`
2. Python 测试禁止硬编码 warmup 与 `allow_internal_nan`。
3. 预热/非预热分段断言：
   - 单指标口径：先用 `run_ranges[source].warmup_range` 确定预热段长度（执行态真值）
   - 再断言 `required_warmup_bars` 与该长度一致
   - `allow_internal_nan=false`：预热段全 `null/NaN`，非预热段无 `null/NaN`
   - `allow_internal_nan=true`：预热段全 `null/NaN`，非预热段跳过 NaN/null 校验
   - 主校验列由 Rust 契约导出，Python 测试不硬编码列名

### 3.2 构建与 mapping 专项

1. mapping 全长语义保持。
2. 硬校验仅绑定非预热 `data_range`。
3. 预热段不做覆盖硬校验。
4. `run_ranges` 始终是 source 自身相对索引。
5. `base_data_key` 必须是最小周期（更高频 source 直接失败）。

### 3.3 切片/拼接专项

1. `slice_pair_by_base_range` 成对同步。
2. `base_range` 切片后 `run_ranges` 重建正确。
3. `concat_data_containers + concat_backtest_summaries` 时间轴一致。
4. stitched 资金列重建后无伪跳变。

### 3.4 WF 专项

1. 两模式窗口模板与平移公式正确。
2. 第一窗与后续窗统一同一算法。
3. `WalkForwardConfig` 字段契约校验：
   - 必须存在：`train_bars/test_bars/test_warmup_source/inherit_prior/optimizer_config`
   - 必须不存在：`transition_bars`
4. 测试执行链固定：
   - `run_single_backtest(ExecutionStage::Signals)`
   - 注入
   - `backtester::run_backtest`
   - `performance_analyzer::analyze_performance`
5. 注入点唯一且合法。
6. 不满足跨窗判定不注入开仓。
7. `window_results` 与 `stitched_result` 只含非预热测试段。
8. stitched 主路径与二次路径 `time` 一致。

### 3.5 异常/边界专项（负面用例）

1. `source` 任意列含 `null/NaN`，`build_data_container` 必须直接报错。
2. 非预热段映射出现 `null`，必须直接报错。
3. 覆盖不足（首或尾不满足）必须直接报错。
4. 窗口不足以容纳完整 `train+test` 必须直接报错。
5. `test_bars < 2`（无法注入倒数第二根）必须直接报错。
6. `test_warmup` 长度为 `0`（无法注入 warmup 末根）必须直接报错。
7. 第一窗无上窗状态时，继承开仓注入必须跳过且不报错。

---

## 4. 必保留 pytest 清单

以下用例必须保留并持续通过：

1. `py_entry/Test/backtest/test_walk_forward_guards.py`
2. `py_entry/Test/backtest/precision_tests/test_balance.py`
3. `py_entry/Test/backtest/precision_tests/test_capital_consistency.py`
4. `py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`

---

## 5. 必增 pytest 清单

1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
   - 验证 `resolve_indicator_contracts` 契约输出
   - 验证 warmup 与 `allow_internal_nan` 分段行为
2. `py_entry/Test/backtest/common_tests/test_slice_and_concat_contracts.py`
   - `base_range` 切片后 `run_ranges` 重建
   - 成对切片与时间轴一致
3. `py_entry/Test/backtest/test_walk_forward_new_pipeline.py`
   - Signals 阶段截断
   - 注入点约束
   - 注入后二次执行链约束
   - WalkForwardConfig 字段契约断言（无 `transition_bars`）
4. `py_entry/Test/backtest/test_build_container_fail_fast.py`
   - source `null/NaN` 失败
   - 非预热映射 `null` 失败
   - 覆盖不足失败

---

## 6. 运行顺序

1. `just check`（A0 前置：先保证指标契约与类型编译通过）
2. `just test-py path="py_entry/Test/indicators/test_indicator_warmup_contract.py"`
3. `just test-py path="py_entry/Test/backtest/test_walk_forward_guards.py"`
4. `just test-py path="py_entry/Test"`
5. `just test`

---

## 7. 验收标准

1. pytest 主链通过。
2. Rust 辅助测试通过。
3. 指标契约、构建校验、WF 链路三块均有用例覆盖。
4. 所有失败场景都能 Fail-Fast 且错误可定位。
5. L5 性能门槛通过且无回归。
