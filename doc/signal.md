# 信号模块文档
## 概述
信号模块旨在通过一个JSON配置文件描述多时间框架策略，利用Polars库的矢量化计算自动生成交易信号。


## 信号模板JSON配置（交易规则）

### 多周期信号模版示例
```json
{
  "name": "multi_timeframe_strategy",
  "enter_long": [
    {
      "logic": "and",
      "conditions": [
        {
          "compare": "GT",
          "a": { "name": "sma_0", "source": "ohlcv_2", "offset": 0 },
          "b": { "name": "sma_1", "source": "ohlcv_2", "offset": 0 }
        },
        {
          "compare": "GT",
          "a": { "name": "rsi_0", "source": "ohlcv_1", "offset": 0 },
          "b": { "param": "rsi_midline" }
        },
        {
          "compare": "CGT",
          "a": { "name": "close", "source": "ohlcv_0", "offset": 0 },
          "b": { "name": "bbands_0_upper", "source": "ohlcv_0", "offset": 0 }
        }
      ]
    }
  ],
  "exit_long": [],
  "enter_short": [],
  "exit_short": []
}
```

- **name**：策略名称，用于标识。
  - **enter_long/exit_long/enter_short/exit_short**：每个字段是一个信号组数组。如果为空，则对应信号默认为全false向量。
  - **logic**：组内条件的组合逻辑，支持"and"（所有条件必须满足）和"or"（任一条件满足）。
  - **conditions**：条件列表，每个条件包括比较操作符（compare）、左操作数（a）和右操作数（b）。
  - **a**：始终为数据操作数，格式为
    - {name: 列名, source: 数据源如"ohlcv_0", offset: 偏移量}。
  - **b**：可为数据操作数（同a）或参数操作数
    - {param: 参数名}
    - 参数需在信号参数配置中映射为数值。

### 信号组合模版示例:
```json
{
  "name": "adx_switch_strategy",
  "enter_long": [
    {
      "logic": "and",
      "conditions": [
        {
          "compare": "GT",
          "a": { "name": "adx_0", "source": "ohlcv_0", "offset": 0 },
          "b": { "param": "adx_threshold" }
        },
        {
          "compare": "CGT",
          "a": { "name": "sma_0", "source": "ohlcv_0", "offset": 0 },
          "b": { "name": "sma_1", "source": "ohlcv_0", "offset": 0 }
        }
      ]
    },
    {
      "logic": "and",
      "conditions": [
        {
          "compare": "LT",
          "a": { "name": "adx_0", "source": "ohlcv_0", "offset": 0 },
          "b": { "param": "adx_threshold" }
        },
        {
          "compare": "CLT",
          "a": { "name": "sma_0", "source": "ohlcv_0", "offset": 0 },
          "b": { "name": "sma_1", "source": "ohlcv_0", "offset": 0 }
        }
      ]
    }
  ],
  "exit_long": [],
  "enter_short": [],
  "exit_short": []
}
```

多个信号组默认用OR触发：任一组满足即触发信号。该设计支持策略切换，例如基于不同市场条件（如ADX阈值）定义多个组。


## 信号参数JSON配置

参数配置是一个键值对对象，用于映射策略中的参数名到具体数值。

示例配置：

```json
{
  "rsi_midline": 50,
  "adx_threshold": 20
}
```
参数必须覆盖所有策略中使用的param字段，否则系统应报告缺失参数错误。


## 策略解释

以示例配置为例，该策略名为"multi_timeframe_strategy"，仅定义做多进场条件：
  - 组内逻辑为"and"，要求所有条件同时满足。
  - 条件1：在"ohlcv_2"数据源中，短期均线"sma_0"大于长期均线"sma_1"（表示趋势向上）。
  - 条件2：在"ohlcv_1"数据源中，RSI指标"rsi_0"大于参数"rsi_midline"（映射为50，表示超买/超卖中线以上）。
  - 条件3：在"ohlcv_0"数据源中，收盘价"close"刚刚向上穿越布林带上轨"bbands_0_upper"（使用CGT操作符，表示当前满足而前一周期不满足）。

数据源命名约定：ohlcv_0为最小周期，ohlcv_1为较大周期，以此类推。指标命名如sma_0（短期）、sma_1（长期）。

在理想状态下，策略应扩展支持exit_long等字段，例如定义离场条件如RSI低于阈值或价格穿越均线。

## 可用比较操作符

支持以下比较操作符，用于条件评估：

- **GT**：大于（>）
- **LT**：小于（<）
- **GE**：大于等于（>=）
- **LE**：小于等于（<=）
- **EQ**：等于（==）
- **NE**：不等于（!=）
- **CGT**：刚刚大于（当前>且前一周期不>）
- **CLT**：刚刚小于（当前<且前一周期不<）
- **CGE**：刚刚大于等于（当前>=且前一周期不>=）
- **CLE**：刚刚小于等于（当前<=且前一周期不<=）
- **CEQ**：刚刚等于（当前==且前一周期不==）
- **CNE**：刚刚不等于（当前!=且前一周期不!=）

交叉操作符（如CGT）用于检测信号穿越，确保捕捉动态变化。

## 设计细节与规范

在理想项目状态下，信号生成应遵循以下约束和行为：

- **矢量化处理**：所有计算使用Polars矢量化操作，避免循环，提升性能。
- **数据查找顺序**：列名（如"close"或"sma_0"）首先在指标结果中查找，若未找到则在OHLCV数据源中查找。若仍未找到，应报告错误并提供提示（如"列名未找到，请检查数据源"）。
- **偏移量处理**：offset必须为非负整数（0表示当前周期，1表示前一周期）。负值应被禁止，以避免使用未来数据。偏移通过向过去移位实现。
- **NaN值处理**：如果任何操作数在某点为NaN，则该点信号默认为false，确保信号鲁棒性并避免NaN传播。
- **数据映射**：对于多时间框架数据，系统应应用映射表（从processed_data.mapping中获取）将数据对齐(一般是ohlcv的最小周期)。若配置指定跳过映射，则直接使用原始数据。该机制确保跨周期一致性。
  - 先用processed_data.skip_mapping检测是否需要映射, 如不需要可以跳过映射
- **操作数解析**：左操作数（a）始终指向数据列。右操作数（b）可指向数据列或参数（通过signal_params映射）。解析失败应报告具体错误，如"参数未找到"或"数据源索引越界"。
- **信号组合**：组内条件按logic组合（AND为所有满足，OR为任一满足）。多个组的结果通过OR聚合，任一组满足即触发信号。如果无组定义，返回全false向量。
- **输出格式**：返回一个DataFrame，包含四个布尔列：enter_long、exit_long、enter_short、exit_short，每列长度与数据源匹配。
- **错误处理**：系统应提供描述性错误，如无效源格式、列缺失或类型转换失败，确保用户易于调试。
- **扩展性**：理想状态下，支持更多逻辑运算（如NOT）和嵌套组，但当前限制为简单AND/OR以保持简洁。

该设计确保项目高效、可靠，并易于维护和扩展。
