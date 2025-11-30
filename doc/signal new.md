@templates.py#L14-25
旧

@dataclass
class SignalTemplate:
    """信号模板 - 对应 Rust SignalTemplate"""

    name: str
    enter_long: Optional[List[SignalGroup]] = None
    exit_long: Optional[List[SignalGroup]] = None
    enter_short: Optional[List[SignalGroup]] = None
    exit_short: Optional[List[SignalGroup]] = None
新
    enter_long: Optional[SignalGroup] = None
     exit_long: Optional[SignalGroup] = None
     enter_short: Optional[SignalGroup] = None
     exit_short: Optional[SignalGroup] = None
 
@custom_backtest.py#L90-122 
舍弃旧的复杂的模版构建, 改用字符串模版简单构建

新版如下
py端直接传参如下格式, 然后在rust端解析
SignalGroup(
    logic_op='AND',
    comparisons=[
        "close,ohlcv_15m > close,ohlcv_15m,&1-3",
        "sma_0,ohlcv_15m > sma_1,ohlcv_15m",
        # 字符串不递归
    ],
    sub_groups=[
        SignalGroup(logic_op='OR', comparisons=['rsi > 70'], sub_groups=[]),
        # ... 更多嵌套组, sub_groups可递归
    ]
)


op决定了, comparisons内部元素的关系
, 以及sub_groups内部元素的关系
, 以及comparisons和sub_groups的关系

close,ohlcv_15m,&1-3"
第一个位置, 是指标名, 第二个位置是数据源的名字, 第三个位置是偏移量

偏移量语法
偏移量可以留空, 留空就保持不变
如果是1, 意味着普通偏移量是1, 相当于shift(1)
如果是 &1-2, 意味着, 偏移范围1, 2, 3, 都要符合条件才行
如果是 |1-2, 意味着, 偏移范围1, 2, 3, 任一条件就行

偏移量合法写法示例
偏移量是>=0的正整数, 0代表无偏移
省略默认为0
"close,ohlcv_15m,1 > close,ohlcv_15m"
"close,ohlcv_15m,1 > close,ohlcv_15m,2"
"close,ohlcv_15m,&1-3 > close,ohlcv_15m"
"close,ohlcv_15m,&1-3 > close,ohlcv_15m,1"
"close,ohlcv_15m,&1-3 > close,ohlcv_15m,&2-4", (需要左右两边都是&, 或都是|, 否则报错), (需要1-3和2-4, 虽然起点不同但是长度相等, 否则报错)

跟左右顺序无关, 可以左右颠倒依然合法, 如
"close,ohlcv_15m,1 > close,ohlcv_15m"
相当于
"close,ohlcv_15m < close,ohlcv_15m,1"



字符串不递归, dataclass递归
SignalGroup是dataclass, 无需解析器解析, dataclass直接用pyo3去映射到Rust端就行了, 解析器只需要处理字符串模版就行了, 递归由SignalGroup自然映射, 无需解析器处理

经过研究决定用rust nom做高性能的字符串模版解析

如"rsi,ohlcv_15m > $rsi_middle",
如果有$开头的名字, 就说明是数值参数, 需要进行数值参数映射, 参数映射方式和旧的方式是一样的, 只是模版语法不同
也可以写成这样,  如"rsi,ohlcv_15m > 70", 检测到数字就直接进行比较就行了

支持逻辑取反
"!close,15m > open,15m" (收盘价不高于开盘价)