# 阶段计划

## Gate 0：Spec 审阅

目标：人工确认指标测试系统的新 oracle 模型、冻结语义和迁移边界。

验收条件：

1. 主校验源单选规则确认。
2. 四级 strict exact oracle 优先级确认。
3. `local_csv` 后备规则确认。
4. secondary oracle assertion 规则确认。
5. expected different 精确识别 comparison mismatch 的规则确认。
6. warmup 专用测试与 comparison case 的数值真值解耦规则确认，并确认 `resolve_indicator_contracts(...)` 是全局 warmup 真值入口。
7. local CSV 数据模式、`Path` 类型数据来源与 fixture resolver 规则确认。
8. Pydantic 严格模型与 adapter 回调输入输出强类型边界确认。
9. 默认行为与特殊处理边界确认。
10. 失败上下文输出契约确认。
11. 默认 3 个标准 case 的参数与数据覆盖规则确认。
12. 全局 warmup 冻结项归属确认。
13. 语义新增与冻结清单确认。

未通过本 Gate 前不得进入代码实现。

## Gate 1：AI pre-review

目标：执行前核对 Spec 与当前代码范式。

验收条件：

1. 审阅 `00_meta / 01_context / 02_spec / 03_execution`。
2. 核对当前指标测试主链路。
3. 核对冻结清单是否足以作为最低审查基线。
4. 核对特殊处理清单是否覆盖已知例外入口。
5. 报告清单外风险。

## 阶段 1：现有测试语义盘点

目标：建立当前指标测试行为基线。

影响范围：

```text
py_entry/Test/indicators
py_entry/Test/utils/comparison_tool.py
```

验收条件：

1. 列出现有指标 case。
2. 标记当前 positive / negative 对比语义。
3. 标记多输出列映射。
4. 标记 warmup contract 覆盖情况。

## 阶段 2：新 case contract 与 helper 落地

目标：建立新测试系统骨架。

验收条件：

1. 新 helper 仍通过正式回测链路取得 engine 输出。
2. 现有 comparison helper 语义被复用或最小增强，不重写一套平行比较系统。
3. strict exact comparison 不支持 similarity。
4. `local_csv` 支持 exact / similarity。
5. `LocalCsvOracle` 不暴露重复 `path` 或 `similarity_api`，本地 CSV 数据来源使用 `Path`。
6. secondary oracle assertion 作为附加断言存在。
7. expected different 不使用宽泛异常捕获。
8. 失败输出满足短上下文契约。
9. case 与 adapter 回调边界使用 Pydantic 严格模型，并配合静态类型标注。

## 阶段 3：试点迁移

目标：用少量代表指标验证新系统。

建议试点：

1. `sma`：单输出、应 strict exact。
2. `ema`：单输出、talib 路径敏感。
3. `bbands`：多输出。
4. `atr` 或 `adx`：存在 `talib=true / false` 差异诉求。

验收条件：

1. 试点指标覆盖 positive oracle。
2. 至少一个指标覆盖 expected different assertion。
3. 至少一个多输出指标覆盖完整输出映射。
4. pytest 参数化 id 能直接定位指标、参数、数据集和主校验源。
5. comparison case 不内联 warmup 数值真值。
6. 单个 pytest case 内部没有隐藏 dataset 循环。

## 阶段 4：全量迁移

目标：将现有普通指标测试迁移到新系统。

验收条件：

1. 已有正向一致测试未放宽。
2. 已有预期不一致测试已迁移为 expected different assertion。
3. warmup contract 测试语义保持，运行时输出校验继续消费 `resolve_indicator_contracts(...)` 返回的 contract。
4. warmup scaling scan 与布尔 false 回归检查收口到共享全局 warmup 测试。
5. 旧的模糊 `assert_mode_*` 长期口径退出。
6. 所有特殊处理都有注释与审查记录。

## 阶段 5：04-16 集成准备

目标：让 04-16 的新增指标测试引用新系统。

验收条件：

1. 更新 04-16 文档中的测试契约引用。
2. KC 测试计划改为基于新 case contract。

## 阶段 6：验证与 post-review

目标：完成正式验证和重构漂移审查。

验收条件：

1. `just check` 通过。
2. `just test-py py_entry/Test/indicators` 通过。
3. 冻结清单逐项核对。
4. 完整 diff 审查完成，未发现未声明语义漂移。
5. 失败上下文输出抽样检查通过。
