# Phase 1 执行文档：指标契约与指标测试先落地

## 1. 目标

先把“指标预热真值 + NaN 豁免真值”做成稳定基线，不改容器结构，不改 WF 主流程。

## 2. 本阶段范围

1. 扩展 `Indicator trait`：
   - `required_warmup_bars(params) -> usize`
   - `allow_internal_nan() -> bool`
2. 为当前 registry 全部指标实现上述两项契约（不得遗漏）。
3. 实现唯一导出函数：
   - `resolve_indicator_contracts(indicators_params, base_data_key) -> IndicatorContractSnapshot`
4. 通过 PyO3 暴露契约函数，Python 侧只消费 Rust 导出值。
5. 新增/更新指标专项测试（Rust + pytest）：
   - warmup 契约一致性
   - `allow_internal_nan` 行为一致性

## 3. 非目标（明确不做）

1. 不改 `DataContainer` / `BacktestSummary` 字段结构。
2. 不改 `mapping` 构建流程。
3. 不改回测执行链与 WF 执行链。

## 4. 实施步骤

1. 改 trait 和指标实现。
2. 落地 `IndicatorContractSnapshot` 与 `resolve_indicator_contracts`。
3. PyO3 导出并更新 `.pyi`。
4. 补指标专项测试：
   - 单指标口径：主校验列按 `run_ranges` 切段断言；
   - 断言 `required_warmup_bars` 与预热段长度一致；
   - `allow_internal_nan=false`：预热段全空、非预热段无空；
   - `allow_internal_nan=true`：预热段全空、非预热段跳过空值校验。

## 5. 验收命令

1. `just check`
2. `just test-py path="py_entry/Test/indicators/test_indicator_warmup_contract.py"`
3. `just test`（确认无意外回归）

## 6. 完成标准

1. Rust 与 Python 均不再硬编码 warmup 规则。
2. 指标契约函数与测试稳定通过。
3. 不引入容器/WF 侧行为变化。

## 7. 风险与应对

1. 风险：warmup 公式与现实现差 1。
   应对：以“当前 Rust 指标实现行为”为唯一基准，测试先锁死。
2. 风险：新增指标后忘记补契约。
   应对：registry 全量遍历测试，缺项直接 fail。
