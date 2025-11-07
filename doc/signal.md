## 信号模块：用一个简单例子来说明一切
  * 用一个配置文件描述多周期策略, 交易信号生成器自动处理

## 示例信号模版JSON配置(交易规则)

{
  "name": "multi_timeframe_dynamic_strategy",
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
  ]
}

## 示例信号参数JSON配置
{
  "rsi_midline": 50
}

## 策略解释
- **策略名字**：multi_timeframe_dynamic_strategy（多时间框架动态策略）。
- **为了简化,目前只定义了做多, enter_long, 还可以定义, exit_long, enter_short, exit_short
- 如果logic为and, 那么group条件需要全部满足, 才能把enter_long对应索引设为true
  - logic为or, group条件只需要满足一个,就可以把enter_long对应索引设为true
  1. **第一条**：在“ohlcv_2”这个数据源里，“sma_0”这根均线 > “sma_1”那根均线。（比如，周线快均线超过慢均线。）
    * 一般sma_0是短期均线, sma_1是长期均线, ohlcv_0是小周期数据, ohlcv_1是多周期数据, 以此类推
  2. **第二条**：在“ohlcv_1”数据源里，“rsi_0”指标 > “rsi_midline”(在参数中映射成50)
    * rsi_midline需要在信号参数里映射成50
  3. **第三条**：在“ohlcv_0”数据源里，收盘价“close”**刚刚向上穿过**布林带上轨“bbands_0_upper”。（CGT表示“交叉大于”，今天满足、昨天不满足。）
    * GT表示大于, CGT表示, 刚刚上穿

## 可用符号如下
```
GT = "GT"  # >
LT = "LT"  # <
GE = "GE"  # >=
LE = "LE"  # <=
EQ = "EQ"  # ==
NE = "NE"  # !=
CGT = "CGT"  # > 交叉
CLT = "CLT"  # < 交叉
CGE = "CGE"  # >= 交叉
CLE = "CLE"  # <= 交叉
CEQ = "CEQ"  # == 交叉
CNE = "CNE"  # != 交叉
```

## 设计细节
  * 用polars矢量化进行数组处理, 不用for循环
  * 列名先从指标数据中查找, 找不到从ohlcv数据中查找, 查找不到直接报错,并附带提示信息
  * 策略应该返回4个布尔数组,enter_long, exit_long, enter_short, exit_short
    * nan传播问题, 如果某索引处遇到nan, 那么某索引处默认为false
  * offset不能为负数, 避免未来数据, offset=1表示上个周期的数据,以此类推
  * compare比较时, a是左边, b是右边
  * 左边a,只有一种形式,指向数组,右边b有两种形式,指向数组或指向参数,指向参数时需要映射
  * enter_long接受数组, 也就是接受多个策略组合, 任一满足即可触发
    * 场景如针对不同行情切换策略, enter_long: [ 策略1  `adx > 20 and sma_0 > sma_1`, 策略2 用 `adx <= 20 and rsi_0 < rsi_lower` ]



文件放到 src/backtest_engine/signal_generator 文件夹下面, 并且需要把文件拆分成合适的大小, 提高可维护性

把方案拆分成细粒度
把大文件拆分成多个小文件, 每个文件不要超过200-300行
把大任务拆分成小任务
调用子任务Code处理
每次子任务只实现一个小任务, 只处理一个文件
告诉子任务, 忽略过程中的编译报错, 优先执行任务


首先帮我看一下, 当前项目的模块架构是否符合方案

调用子任务ask, 看当前项目模块架构是否符合方案, 每个细节都要检查, 如果不符合就给出更新建议, 力求模块尽量符合方案
每个文件都要检查, 从mod.rs入手递归排查

还要检查有没有什么优化空间
比如有没有不必要的clone之类的
比如有没有不应该的参数硬编码
比如函数传参是否正确
比如有没有不必要的冗余写法之类的
比如有没有未使用的遗留旧代码之类的
比如检查是否存在死代码,被定义但未被调用,是遗留的旧代码,还是尚未完成的代码


提出重构需要谨慎, 只在以下情况重构
当前架构已经非常不适合方案,需要重构,需要给出明确的理由,才被接受
当前架构非常样板代码过多,可以通过重构简化,前提只是简单的简化,不要搞复杂封装
当前文件太长,需要重构,最好只是简单的拆分文件,没必要复杂封装
如果只是简单的通过修改细节就能修复,就不要重构
总之, 优先修复细节问题,谨慎对待重构,保持代码风格简单清晰,大文件要拆分成模块化架构,最好不要超过200行

不要用#[allow(unused)]等allow方法, 因为只会掩盖问题, 应该解决实际问题, 或者用注释标注未来解决

还要去排查 @problems  这些警告是可以直接修复的小问题, 还是表示有重大逻辑缺陷, 给出建议
记住, 只修复 src/backtest_engine/signal_generator 这个模块的静态编译警告, 其他模块都不要动

必须阅读回测模块的源代码, 才能生成方案, 不能只看表面, 否则方案不被接受

子任务ask只返回方案和建议, 不执行任何代码修改
