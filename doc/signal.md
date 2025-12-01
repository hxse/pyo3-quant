# 信号生成系统文档

本文档描述了当前系统中信号生成的逻辑、数据结构和配置语法。

## 1. 核心数据结构

信号生成的核心配置结构对应 Rust 代码中的 `SignalTemplate` 和 `SignalGroup`。

### SignalTemplate (信号模板)

`SignalTemplate` 是顶层配置对象，定义了一个策略的四个主要信号触发点。

```python
@dataclass
class SignalTemplate:
    name: str
    # 多头入场信号组
    enter_long: Optional[SignalGroup] = None
    # 多头出场信号组
    exit_long: Optional[SignalGroup] = None
    # 空头入场信号组
    enter_short: Optional[SignalGroup] = None
    # 空头出场信号组
    exit_short: Optional[SignalGroup] = None
```

### SignalGroup (信号组)

`SignalGroup` 是一个递归结构，用于组合多个条件。它支持 `AND` 或 `OR` 逻辑来连接内部的比较条件和子信号组。

```python
@dataclass
class SignalGroup:
    # 逻辑运算符: 'AND' 或 'OR'
    logic: str 
    # 字符串格式的比较条件列表
    comparisons: List[str]
    # 嵌套的子信号组列表
    sub_groups: List['SignalGroup']
```

**逻辑说明：**
- `logic='AND'`: `comparisons` 中的所有条件 **以及** `sub_groups` 中的所有子组都必须满足。
- `logic='OR'`: `comparisons` 中的任一条件 **或者** `sub_groups` 中的任一子组满足即可。

---

## 2. 信号条件字符串语法

`comparisons` 列表中的每个字符串代表一个具体的比较条件。系统使用高性能解析器（基于 Rust `nom`）来处理这些字符串。

**基本语法格式：**
```text
[!] 左操作数 运算符 右操作数
```

### 2.1 左操作数 (Left Operand)

左操作数必须是**数据操作数**。

**格式：** `指标名, 数据源名 [, 偏移量]`

- **指标名 (name)**: 如 `close`, `open`, `rsi`, `sma_0` 等。
- **数据源名 (source)**: 如 `ohlcv_15m`, `ohlcv_1h` 等。
- **偏移量 (offset)**: (可选) 指定取历史数据的偏移。默认为 0（当前K线）。

**偏移量语法：**

| 语法 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `N` | 单个值 | 取前 N 根K线的值 | `1` (前一根), `0` (当前) |
| `&start-end` | 范围 AND | 范围内**所有**偏移都必须满足条件 | `&1-3` (偏移1, 2, 3 都需满足) |
| `\|start-end` | 范围 OR | 范围内**任一**偏移满足条件即可 | `\|1-3` (偏移1, 2, 3 任一满足) |
| `&v1/v2/v3` | 列表 AND | 列表中**所有**偏移都必须满足条件 | `&1/3/5` (偏移1,3,5都需满足)|
| `\|v1/v2/v3` | 列表 OR | 列表中**任一**偏移满足条件即可 | `\|1/3/5` (偏移1,3,5任一满足) |

### 2.2 运算符 (Operators)

支持普通比较和交叉（Cross）比较。

**普通比较：**
- `>` (大于)
- `<` (小于)
- `>=` (大于等于)
- `<=` (小于等于)
- `==` (等于)
- `!=` (不等于)

**交叉比较 (Cross)：**
表示当前状态满足条件，且上一状态不满足条件（即发生了状态穿越）。
- `x>` (向上突破): 上一根K线 `<=`, 当前K线 `>`
- `x<` (向下跌破): 上一根K线 `>=`, 当前K线 `<`
- `x>=`, `x<=`, `x==`, `x!=`: 同理

### 2.3 右操作数 (Right Operand)

右操作数可以是以下三种类型之一：

1.  **数据操作数**: 格式同左操作数。
    - 例: `open, ohlcv_15m, 1`
2.  **数值字面量**: 直接写数字。
    - 例: `70`, `0.5`, `-100`
3.  **参数引用**: 以 `$` 开头的变量名，引用策略参数。
    - 例: `$rsi_threshold`, `$stop_loss_pct`

### 2.4 逻辑否定 (Negation)

在条件字符串最前面加 `!` 表示对整个条件取反。
- 例: `! close, 15m > open, 15m` (等价于收盘价不大于开盘价)

---

## 3. 示例

### 基础比较
```text
"close, ohlcv_15m > sma_0, ohlcv_15m"
# 当前15分钟收盘价 大于 当前SMA
```

### 带偏移量的比较
```text
"close, ohlcv_15m > close, ohlcv_15m, 1"
# 当前收盘价 大于 前一根收盘价 (上涨)
```

### 交叉信号 (金叉/死叉)
```text
"sma_0, ohlcv_15m x> sma_1, ohlcv_15m"
# 快线(sma_0) 向上突破 慢线(sma_1)
```

### 使用参数
```text
"rsi, ohlcv_1h < $rsi_oversold"
# 1小时RSI 小于 参数rsi_oversold定义的数值
```

### 范围条件 (连续满足)
```text
"close, ohlcv_15m, &1-3 > sma_0, ohlcv_15m, &1-3"
# 过去3根K线(偏移1,2,3)的收盘价都大于对应的SMA
```

### 范围条件 (任一满足)
```text
"volume, ohlcv_15m, |0-2 > $vol_threshold"
# 最近3根K线中，至少有一根的成交量大于阈值
```

### 复杂组合示例 (Python 代码)

```python
SignalGroup(
    logic='AND',
    comparisons=[
        # 1. 价格在均线之上
        "close,ohlcv_15m > sma_0,ohlcv_15m",
        # 2. RSI 低于 70
        "rsi,ohlcv_15m < 70"
    ],
    sub_groups=[
        # 3. 子条件：MACD金叉 或者 成交量放大
        SignalGroup(
            logic='OR',
            comparisons=[
                "macd,ohlcv_15m x> signal,ohlcv_15m",
                "volume,ohlcv_15m > volume,ohlcv_15m,1"
            ],
            sub_groups=[]
        )
    ]
)
```