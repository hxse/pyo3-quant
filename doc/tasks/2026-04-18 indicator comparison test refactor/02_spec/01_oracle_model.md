# Oracle 模型

## 1. 术语

本任务区分两组概念：

1. **四级 strict exact oracle**：指 `pandas-ta` 与 `pandas-ta-classic` 的四种严格对齐来源。
2. **主校验源**：每个 case 实际执行的唯一主校验来源。它可以是四级 strict exact oracle 之一，也可以是 `local_csv`。

因此，项目里有四级正式 pandas-ta 对齐优先级；测试 case 层面有五种可选主校验源。

## 2. 主校验源

每个指标对比 case 必须且只能声明一个主校验源。

主校验源决定该 case 判断指标是否正确的正式依据。

允许的主校验源：

1. `pandas_ta_talib_true_exact`
2. `pandas_ta_talib_false_exact`
3. `pandas_ta_classic_talib_true_exact`
4. `pandas_ta_classic_talib_false_exact`
5. `local_csv`

## 3. 用户选择与程序执行

四级 strict exact oracle 的项目优先级固定为：

1. `pandas-ta (talib=true)`
2. `pandas-ta (talib=false)`
3. `pandas-ta-classic (talib=true)`
4. `pandas-ta-classic (talib=false)`

上面顺序用于用户和 Spec 判断应选择哪个主校验源。

程序不负责判断“哪个 oracle 应该可用”，不负责自动选择优先级，也不负责降级或回退。

测试代码只执行 case 中声明的主校验源：

1. 目标库不存在，直接报错。
2. 目标函数不存在，直接报错。
3. 目标列不存在，直接报错。
4. 对比失败，直接报错。

只有 manifest 或 pytest 显式标记 skip 时才允许跳过，并且必须写明作用域与原因；禁止静默跳过，禁止通过注释删除 case 或输出列来隐藏跳过。

## 4. 注释说明

用户选择低优先级 oracle 或 `local_csv` 时，必须在测试 case 附近用注释说明更高优先级 oracle 不适用的原因。

该说明服务人工审查，不由程序解析，也不作为运行时降级机制。

## 5. 严格 Oracle

前四类主校验源全部属于 strict exact oracle。

strict exact oracle 禁止使用 similarity、correlation、方向一致率或其他相似性指标作为通过条件。

测试框架不提供给前四类 oracle 使用 similarity 的入口。

## 6. local_csv Oracle

`local_csv` 只在用户确认四级 strict exact oracle 全部不可用时使用。

`local_csv` 是后备交叉验证方式，不改变项目默认以 pandas-ta 对齐的总口径。
