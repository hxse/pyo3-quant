# 任务元信息

## 1. 任务描述

`2026-04-18 indicator comparison test refactor` 聚焦重构内置指标对比测试系统。

本任务不新增指标、不修改生产指标公式、不改变回测引擎运行语义。目标是在复用现有模板化回测链路的前提下，重构并扩展指标测试系统，让每个指标的真值源、比较方式、输出列映射、缺失值口径、预期不一致校验和本地 CSV 后备校验都显式化。

本任务尤其强调：测试框架本身很难再用另一层测试来完整测试，因此必须依赖清晰 Spec、详细冻结清单和人工 diff 审查来避免重构漂移。

## 2. 任务级别

本任务定为 `A 类任务`。

原因：

1. 指标对比测试系统是内置指标真值链的关键基础设施。
2. 该系统会影响当前所有内置指标，以及后续 `2026-04-16 extensible builtin indicators` 中新增指标的验收口径。
3. 测试框架重构容易出现 quietly wrong：测试看似通过，但 oracle 选择、缺失值处理、容差或预期不一致语义发生漂移。
4. 本任务主要依赖 Spec 与审查防止测试框架重构漂移，需要完整 Spec Gate、Execution Gate、阶段执行和 post-review。

## 3. 任务范围

### 范围内

1. 定义指标对比测试的 oracle 模型。
2. 定义严格对齐 oracle 的优先级与选择规则。
3. 定义本地 CSV 后备校验源，以及 exact / similarity 两类比较模式。
4. 定义 secondary oracle assertion，支持 expected same 与 expected different。
5. 定义 case manifest / case contract，使指标测试参数、数据集、输出列映射、truth source、容差和缺失值口径显式化。
6. 冻结当前指标测试系统中必须保持等价的既有语义。
7. 制定后续重构执行计划、文件影响清单、验证计划和 diff 审查清单。
8. 明确本任务完成后，`2026-04-16 extensible builtin indicators` 的指标测试契约应引用新测试系统。

### 范围外

1. 本轮只写 Task 文档，不修改测试代码或生产代码。
2. 本任务不新增 KC 或任何其他生产指标。
3. 本任务不修改任何已有指标公式、输出列、参数名或 warmup contract。
4. 本任务不引入运行时外部自定义指标系统。
5. 本任务不把原始 `talib` 作为正式真值源。
6. 本任务不允许给前四级 pandas-ta / pandas-ta-classic 校验源提供 similarity 功能。
