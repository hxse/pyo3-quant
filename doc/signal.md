# 信号生成系统文档

本文档描述了当前系统中信号生成的逻辑、数据结构和配置语法。

## 1. 核心数据结构

信号生成的核心配置结构对应 Rust 代码中的 `SignalTemplate` 和 `SignalGroup`。

### SignalTemplate (信号模板)

`SignalTemplate` 是顶层配置对象，定义了一个策略的四个主要信号触发点。

```python
@dataclass
class SignalTemplate:
    # 多头入场信号组
    entry_long: Optional[SignalGroup] = None
    # 多头出场信号组
    exit_long: Optional[SignalGroup] = None
    # 空头入场信号组
    entry_short: Optional[SignalGroup] = None
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

**格式：**
1. **简化写法**：`指标名`
   - 隐含默认数据源（`DataContainer.base_data_key`）
   - 隐含偏移量 0
   - 示例：`close` 等价于 `close, [默认源], 0`

2. **完整写法**：`指标名, 数据源名, 偏移量`
   - 必须包含两个逗号。
   - **数据源名**：可留空（如 `close, , 0`），留空时使用默认数据源。
   - **偏移量**：可留空（如 `close, ohlcv_15m, `），留空时默认为 0。

**注意**：逗号必须**全部出现**（2个）或**全部不出现**（0个）。不允许只出现1个逗号（如 `close, ohlcv_15m` 是非法的）。

- **指标名 (name)**: 如 `close`, `open`, `rsi`, `sma_0` 等。
- **数据源名 (source)**: 如 `ohlcv_15m`, `ohlcv_1h` 等。
- **偏移量 (offset)**: 指定取历史数据的偏移。

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
逻辑公式：`Trigger = (NOT Prev_Satisfied) AND (Curr_Satisfied)`

- `x>` (向上突破): 上一根K线 `<=`, 当前K线 `>`
- `x<` (向下跌破): 上一根K线 `>=`, 当前K线 `<`
- `x>=`: 上一根K线 `<`, 当前K线 `>=`  (注意: `NOT >=` 等价于 `<`)
- `x<=`: 上一根K线 `>`, 当前K线 `<=`  (注意: `NOT <=` 等价于 `>`)
- `x==`: 上一根K线 `!=`, 当前K线 `==`
- `x!=`: 上一根K线 `==`, 当前K线 `!=`

> [!IMPORTANT]
> **NaN/Null 值处理**：交叉信号仅在当前值和前一个值都有效（非 NaN/Null）时才会触发。
> 如果前一个值是 NaN 或 Null，即使当前值满足条件，也**不会**触发交叉信号。
> 这确保了交叉信号仅在发生真实的状态转换时触发，而不是在数据预热期结束后立即触发。

**区间穿越 (Zone Cross)：**

交叉比较的扩展形式。普通交叉（`x> value`）只在穿越发生的那一根K线返回 True（瞬时信号），区间穿越在穿越后**持续返回 True**，直到值离开指定区间（方向信号）。

**语法：**
```text
左操作数 x> 激活边界..终止边界
左操作数 x< 激活边界..终止边界
```

`..` 是范围分隔符，第一个值为激活边界，第二个值为终止边界。

**语义：**

| 语法 | 激活条件 | 活跃区间 | 失效条件 |
| :--- | :--- | :--- | :--- |
| `x> lower..upper` | `prev <= lower AND curr > lower` | `lower < value < upper` | `value >= upper` 或 `value <= lower` |
| `x< upper..lower` | `prev >= upper AND curr < upper` | `lower < value < upper` | `value <= lower` 或 `value >= upper` |
| `x>= lower..upper` | `prev < lower AND curr >= lower` | `lower <= value <= upper` | `value > upper` 或 `value < lower` |
| `x<= upper..lower` | `prev > upper AND curr <= upper` | `lower <= value <= upper` | `value < lower` 或 `value > upper` |

**再激活**：值离开区间失效后，如果再次满足穿越条件，会重新激活。

**范围边界类型**：和右操作数一致，支持数值字面量、数据操作数、参数引用（`$`）。

**典型示例：**

- **RSI 超卖反弹**：`RSI x> 30..70`
  - 激活：RSI 自下而上穿过 30。
  - 活跃：RSI 在 (30, 70) 区间。
  - 失效：RSI 触及 70（获利）或跌破 30（走弱）。
- **均线回踩确认**：`close x> sma_200..sma_50`
  - 激活：价格从下方穿过长期均线（200线）。
  - 活跃：价格保持在长期和短期均线（50线）之间。
  - 失效：价格突破短期均线（趋势加速阶段结束）或跌破长期均线（支撑失败）。

> [!WARNING]
> **约束限制：**
> 1. `..` **仅允许与交叉操作符搭配**（`x>`, `x<`, `x>=`, `x<=`）。普通比较操作符（`>`, `<` 等）不支持 `..`。
> 2. 左操作数的偏移量**仅支持单值**（如 `0`, `1`）。范围偏移量（`&1-3`）和列表偏移量（`|1/3/5`）不允许与 `..` 搭配。(暂时不支持, 未来可能会添加)

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

### 区间穿越 (RSI 方向信号)
```text
"rsi,ohlcv_1h,0 x> 20..60"
# RSI 自下而上穿过20时激活，RSI 在 (20, 60) 区间内持续为 True
# RSI >= 60 或 RSI <= 20 时失效
```

### 区间穿越 (布林带方向信号)
```text
"close,ohlcv_1h,0 x> bbands_lower,ohlcv_1h,0 .. bbands_middle,ohlcv_1h,0"
# 价格自下而上穿过布林下轨时激活
# 价格在 (下轨, 中轨) 区间内持续为 True
# 价格 >= 中轨 或 价格 <= 下轨 时失效
```

### 区间穿越 (做空方向 + 参数引用)
```text
"rsi,ohlcv_1h,0 x< $rsi_high .. $rsi_low"
# RSI 自上而下穿过 $rsi_high 时激活
# RSI 在 ($rsi_low, $rsi_high) 区间内持续为 True
# RSI <= $rsi_low 或 RSI >= $rsi_high 时失效
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

---

## 4. 信号生成输出

`BacktestRunner.run()` 执行完成后，信号生成器会返回一个 `DataFrame`，其中包含以下固定列：

| 列名 | 类型 | 描述 |
| :--- | :--- | :--- |
| `entry_long` | `bool` | 是否触发多头入场信号 |
| `exit_long` | `bool` | 是否触发多头出场信号 |
| `entry_short` | `bool` | 是否触发空头入场信号 |
| `exit_short` | `bool` | 是否触发空头出场信号 |
| `has_leading_nan` | `bool` | **无效数据标记**。在参与信号生成的任何指标、数据、参数中，如果当前位置有 `NaN` 或 `Null`，则标记为 `True`（未参与信号生成的数据不被记录）。 |

**`has_leading_nan` 的作用：**
- 帮助识别策略的“数据预热期”长度。例如使用 SMA(200) 时，前 199 根 K 线的该列通常为 `True`。
- 帮助识别中间缺失的数据或计算异常（如除以零产生的 NaN）。
- **信号完整性**：信号评估逻辑在检测到数据无效时，会同步将该位置的信号设为 `False` 并在 `has_leading_nan` 中标记为 `True`，以保证回测的严格性。
- **传递性**：该列会被自动复制到回测结果 DataFrame 中，作为绩效分析（如计算 `has_leading_nan_count`）的基础数据。
