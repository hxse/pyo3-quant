# Diff 审查清单

本清单来自 `02_spec/06_semantic_delta_and_freeze_list.md`。

它是最低审查基线，不替代完整 diff 审查。

## 1. 主链路核对

审查点：

1. 指标测试是否仍通过正式回测链路取得 engine 输出。
2. 是否仍使用 `ExecutionStage.Indicator`。
3. 是否仍从 `ResultPack.indicators` 读取 engine indicators。
4. 是否仍从同一 `DataPack.source` 读取 oracle 输入数据。

## 2. Oracle 核对

审查点：

1. 每个 case 是否只有一个主校验源。
2. 四级 strict exact oracle 是否没有 similarity 通过路径。
3. 测试框架是否没有自动降级或回退路径。
4. `local_csv` 是否只作为后备 oracle。
5. secondary oracle assertion 是否只用于 pandas-ta / pandas-ta-classic 四级 oracle 路线。
6. secondary `expected_different` 是否精确识别 same comparator 的 comparison mismatch，而不是新增 diff comparator。
7. 是否不存在 `except AssertionError`、`except Exception` 或异常消息字符串匹配来判断 expected different 通过。
8. `LocalCsvOracle` 是否不暴露重复 `path` 或 `similarity_api`。
9. 标准生成数据是否使用具体 `DatasetId`。
10. 本地 CSV 数据来源是否使用 `Path` 类型，而不是字符串 group id。
11. `LocalCsvOracle` 的 CSV schema 是否使用 `oracle_<output>` 输出列。
12. `case_id` 与 `dataset_id` 是否使用文件名安全 id，非法字符是否直接报错。
13. case、oracle、dataset、skip、tolerance 与 adapter 回调输入输出是否有 Pydantic 严格模型和静态类型标注。

## 3. 比较逻辑核对

审查点：

1. strict exact 是否检查长度。
2. strict exact 是否检查输出列映射。
3. strict exact 是否检查全列缺失值 mask。
4. strict exact 是否逐点 `allclose`。
5. 布尔列是否逐点相等。
6. 当前正向一致测试是否没有被放宽。
7. 现有 `comparison_tool.py` 和 `indicator_test_template.py` 的有效校验语义是否被保留或增强。
8. 失败信息是否包含校验模式、指标、列、行、参数、数据源、oracle 和短上下文。

## 4. warmup 核对

审查点：

1. 静态 `resolve_indicator_contracts` 校验是否保留。
2. 运行时输出缺失校验是否保留。
3. `Strict` 非预热段无缺失语义是否保留。
4. `Relaxed` 非预热段不整行全空语义是否保留。
5. warmup scaling scan 是否保留。
6. 布尔 `False` 不被视为缺失值。
7. warmup skip 是否只作为 warmup 专用测试的逃生舱，并有注释与报告。
8. comparison case 是否没有内联 `expected_bars`、`warmup_mode` 或类似 warmup 真值字段。
9. warmup runner 是否复用 `cases.py` 的 `CASES` 与 `warmup_check`，而没有另起 warmup 真值来源。
10. 运行时输出校验是否消费聚合函数返回的 `contract.warmup_bars` 与 `contract.warmup_mode`。
11. warmup scaling scan 是否由共享全局 warmup 测试承载。

## 5. 测试覆盖核对

审查点：

1. 已有指标 case 是否完成迁移。
2. 已有 negative 诉求是否迁移。
3. 多输出指标是否覆盖全部正式输出列。
4. 数据覆盖扩展是否没有改变默认数据生成语义。
5. 每个指标是否默认声明 3 个参数和数据都不同的标准 case。
6. 04-16 的测试契约是否能引用新系统。
7. pytest 参数化输出是否能直接定位失败 case。
8. 每个指标目录是否只有 `test_contracts.py` 一个 pytest 薄入口。
9. `test_contracts.py` 是否固定只包含 `test_accuracy` 与 `test_warmup_contract`。
10. `test_contracts.py` 是否没有额外 pytest `test_*` 函数。
11. `test_contracts.py` 是否只 import `pytest`、共享 runner / `case_id`、本指标 `CASES` 与 `ADAPTER`。
12. `test_contracts.py` 是否没有 case 拼接、筛选、排序、生成、循环、判断、异常处理、取数、计算、比较或报错逻辑。
13. 结构校验是否能在缺入口、缺函数、多余函数、禁止控制流或旧入口残留时明确失败。

## 6. 特殊处理核对

审查点：

1. 是否存在未注释的 `local_csv similarity`。
2. 是否存在未注释的容差放宽。
3. 是否存在未注释的 case skip、列 skip 或 warmup skip。
4. 是否存在通过注释删除 case 来隐藏 skip。
5. 是否存在未报告用户的特殊处理。
6. 是否存在未说明来源的本地 CSV 数据集或 oracle CSV fixture。

## 7. 清单外风险扫描

审查时必须额外查看：

1. 是否引入生产代码改动。
2. 是否引入新的外部自定义指标链路。
3. 是否把原始 `talib` 作为正式真值源。
4. 是否删除了现有测试覆盖。
5. 是否让测试通过条件变宽。
