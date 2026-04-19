# 设计方向

## 1. 收口目标

本任务将指标测试从“每个文件手写一套比较逻辑”收口到“指标目录高内聚 + 共享后台统一执行”。

目标不是追求最少改动，而是让指标测试系统长期可扩展、可审查、可迁移。

每个指标自己的 case、adapter、pytest contract 入口与 fixture 应集中放在该指标目录中。

该结构服务后续扩展和维护：新增一个指标时，优先只新增或审查一个指标目录；共享后台不承载指标特有细节。

共享后台只承载 runner、compare、datasets、reporting、oracle types 等通用能力，不承载指标特有逻辑。

## 2. 核心对象

建议引入 case manifest 概念。

每个指标目录至少包含：

1. `cases.py`：指标 comparison cases。
2. `adapter.py`：该指标的 engine / oracle 取数与格式转换回调。
3. `test_contracts.py`：薄 pytest 入口，固定只承载 `test_accuracy` 与 `test_warmup_contract`。
4. `fixtures/`：该指标自己的本地 fixture。

`test_contracts.py` 只做 pytest 入口：导入 `CASES`、`ADAPTER`、共享 runner 和共享 `case_id`，用固定两个 pytest 函数参数化调用共享 runner。不放 case 拼接、筛选、循环、判断、异常处理、取数、计算、比较或报错逻辑。

共享 pytest / conftest 层应做硬结构校验，确保每个指标目录都有 `test_contracts.py`，且固定只包含 `test_accuracy` 与 `test_warmup_contract` 两个函数。

每个 case 至少表达：

1. 指标 base name 与 indicator key。
2. source key 与数据集。
3. 参数。
4. 主校验源。
5. 输出列映射。
6. 由主校验源派生的比较口径。
7. 容差。
8. 全局缺失值口径及特殊处理注释。
9. secondary oracle assertion，包括 expected same 与 expected different。
10. 显式 skip 注释。

case 不表达 pta 调用细节、engine 输出提取细节或 warmup 数值真值。

## 3. 校验源分层

主校验源只能选择一种：

1. `pandas-ta (talib=true)`
2. `pandas-ta (talib=false)`
3. `pandas-ta-classic (talib=true)`
4. `pandas-ta-classic (talib=false)`
5. `local_csv`

前四类只能严格逐点校验。

`local_csv` 只在前四类都不可用时启用，可选择 exact 或 similarity。

程序不负责判断优先级、不负责降级、不负责回退。用户在测试 case 中声明使用哪一个主校验源；程序只执行该声明，缺库、缺函数、缺列或对比失败都直接报错。

## 4. 审查策略

本任务不依赖“给测试框架再写一层测试”证明正确性。

核心审查方式：

1. Spec 冻结原有必须保持等价的语义。
2. 执行阶段按冻结清单做最低基线核对。
3. post-review 对完整 diff 做全面审查，防止清单外实现漂移。
