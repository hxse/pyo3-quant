# Local CSV Oracle Contract

## 1. 使用条件

`local_csv` 只在以下条件同时满足时使用：

1. 用户已判断四级 strict exact oracle 都不可用。
2. 用户已选择 `local_csv` 作为主校验源。
3. CSV 来源、输入数据、参数和列语义可以被复查。

## 2. CSV 来源

允许来源：

1. 外部交易平台导出的指标结果。
2. 第三方分析工具导出的指标结果。
3. 本地临时脚本生成的交叉验证结果。
4. 人工整理的固定 golden sample。

若 CSV 来自本地脚本，应在 case 附近用注释记录脚本路径或生成方法。

CSV 不能只作为一次性观察结果进入正式测试。

## 3. 数据模式

`local_csv` oracle 支持两种数据模式：

1. 自动生成数据：`dataset_source` 使用具体 `DatasetId`，oracle CSV 由统一 fixture resolver 按 case id 与 dataset id 定位。
2. 本地加载数据：`dataset_source` 使用 `Path("fixtures/local_csv/custom_0.csv")`，同一个 CSV 提供输入数据与 oracle 输出列。

case manifest 中不允许再给 `LocalCsvOracle` 单独写 `path`。

本地 CSV 相对路径默认相对当前指标目录解析。

本地 CSV 文件路径必须由 `Path` 类型的 `dataset_source` 与统一 resolver 决定，避免同一个 case 出现两套路径字段。

自动生成数据模式下，oracle CSV 默认路径由 resolver 固定为：

```text
fixtures/local_csv/oracle/<case_id>/<dataset_id>.csv
```

`case_id` 与 `dataset_id` 必须是文件名安全 id。

允许字符固定为：

```text
A-Z a-z 0-9 _ - .
```

禁止 `/`、`\`、空白、`..` 或任何需要转义才能放进文件名的字符。

resolver 遇到非法 id 必须直接报错，不做自动转义或容错修正。

## 4. CSV Schema

本地加载数据模式下，同一个 CSV 必须至少包含：

1. `open`
2. `high`
3. `low`
4. `close`
5. `volume`
6. `oracle_<output>`

`time` 列可选。

若存在 `time` 列，默认按 `time` 精确对齐。

若不存在 `time` 列，默认按行号对齐。

自动生成数据模式下，oracle CSV 只需要包含 `time` 或行号，以及 `oracle_<output>` 列。

`<output>` 必须来自 case 的 `outputs` 逻辑输出名。

例如 `outputs=["lower", "middle", "upper"]` 时，CSV oracle 列必须是：

```text
oracle_lower
oracle_middle
oracle_upper
```

默认不裁剪行，不自动跳过 warmup，也不自动裁剪首尾不可比区间。

任何非默认对齐、裁剪或列映射都属于特殊处理，必须显式写入 case 附近注释，并在审查报告中列出。

## 5. 比较模式

`local_csv` 支持两种比较模式：

1. `exact`
2. `similarity`

`exact` 模式应尽量复用 strict exact comparison 的长度、缺失值 mask 与逐点 `allclose` 规则。

`similarity` 模式必须使用现成 API，不允许手写相似性算法。

默认只使用一个相关性 API：

```text
pandas_ta.utils.df_error_analysis(...)
```

原因：pandas-ta 自身测试使用该 API 做相关性分析。

若后续需要叠加最大误差、平均误差或分位误差，只能作为特殊处理增加，并且必须在 case 附近注释说明。

默认 similarity 阈值全局统一。

特殊列允许声明更宽阈值，但必须在 case 附近用注释说明原因。

`similarity_api` 不作为 case 参数暴露；后台根据 `compare_mode="similarity"` 固定调用默认 API。

## 6. 对齐规则

CSV case 需要用注释说明：

1. 时间列或行号对齐方式。
2. 输入数据来源。
3. 指标参数。
4. 输出列含义。
5. 是否裁剪 warmup。
6. 是否裁剪首尾不可比区间。

## 7. 限制

`local_csv` 是后备交叉验证，不是默认真值源。

用户判断任一更高优先级 strict exact oracle 可用时，不得使用 `local_csv` 作为主校验源。
