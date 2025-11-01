@/src/backtest_engine/backtester/mod.rs

ohlcv, 有列名如下
time, open, high, low, close, volume
如果列名不存在直接报错
希望这个signal df是只读的, 不要写入, 尽量避免clone
出现nan直接报错

signal, 有4个列名, 布尔数组
enter_long, exit_long, enter_short, exit_short
如果列名不存在直接报错
希望这个signal df是只读的, 不要写入, 尽量避免clone
出现nan直接报错

skip_mask, series, 只读, 不要写入, 尽量避免clone
出现nan直接报错


# 获取参数
1. 从bakctest_params中, 获取参数, 注意, bakctest_params结构体, 不需要设置默认参数, 强制用户传参就行了
2. 获取, sl_pct, tp_pct, tsl_pct, (Param 类型) 代表止损百分比, 止盈百分比, 跟踪止损百分比, 这个百分比是相当于收盘价的
  * key小于等于0, 则不使用该止损方式, 并且不返回该结果列
  * 多头固定止损示例: 止损价 = 进场价 - 进场价 * sl_pct
  * 多头固定止盈示例: 止盈价 = 进场价 + 进场价 * sl_pct
  * 多头跟踪止损示例: 初始跟踪止损价 = 进场价 - 进场价 * sl_pct
  * 多头跟踪止损示例: 更新跟踪止损价 = 锚定高点 - 进场价 * sl_pct
3. 获取, sl_atr, tp_atr, tsl_atr, atr_period, (Param 类型), 代表atr止损的倍数和周期
  * atr倍数和周期如果小于等于0, 则不使用该止损方式, 并且不返回该结果列
  * 多头固定止损示例: 止损价 = 进场价 - ATR * sl_atr
  * 多头固定止损示例: 止盈价 = 进场价 + ATR * sl_atr
  * 多头跟踪止损示例: 初始跟踪止损价 = 进场价 - ATR * sl_atr
  * 多头跟踪止损示例: 更新跟踪止损价 = 锚定高点 - ATR * tsl_atr
4. 获取tsl_use_high, bool, 如果为true, 计算tls时, 以当前k线high为锚点, 为false, 则以当前k线的close为锚点
  * 虽然传统上tsl都是以high价格做锚点减去atr*倍数的, 但是在我的经验中往往close效果更好, 所以添加这个开关
  * tsl_atr用这个选项,  但是tsl_pct不用这个选项, 因为tsl_pct是基于进场价的锚点, 锚点是不变的
5. 获取tsl_per_bar_update, bool, 由于atr是动态的, 如果为True, 那么每个bar都更新tsl, 如果为false, 那么只在突破高低点时更新tsl(是指从进场持仓开始追踪的高低点, 非全局高低点), 只影响tsl_atr, 不影响tsl_pct
6. 获取 exit_in_bar, (bool类型), true表示在指定价格离场 false表示在触发离场的下一个bar的开盘价离场
  * 影响sl, tp, 不影响tsl, tsl只有延迟离场一种方式
7. 获取, initial_capital, (float类型) 代表初始本金(USD)
8. 获取stop_pct, resume_pct, (Param 类型) 分别代表暂停开仓阈值, 回复开仓阈值
  * key小于等于0, 则跳过该功能
9. 获取fee_fixed, fee_pct, (float类型) 代表固定手续费(USD), 百分比手续费

# 在循环中计算仓位
1. 每次只持一个仓位, 可多头可空头可反手, 但是每次只持一个仓位, 不考虑多仓位的问题
2. 每次买入都用全部余额买入, 反手的话, 先计算卖出, 再计算买入, 不考虑杠杆(无杠杆)
3. 手续费只在离场时扣除一次就行了 开仓时无需计算手续费
  * 简单处理, 是为了让用户自行悲观估算, 包含价差滑点网络波动在内的总手续费
4. 先处理信号过滤问题, 再处理优先级问题


# 信号分类
  * 信号触发条件设计, 符合严格进场, 宽松离场
  * 反手信号(平空进多), 需要同bar出现: 存在空头仓位 + enter_long=true + exit_long=false + enter_short=false + exit_short=true或者short方向的sl,tp,tsl任一触发即可, 才成立, 其他情况忽略
  * 反手信号(平多进空), 需要同bar出现: 存在多头仓位 + enter_long=false + exit_long=true或者long方向的sl,tp,tsl任一触发即可, + enter_short=true + exit_short=false, 才成立, 其他情况忽略
  * 多头离场信号, 需要同bar出现: 存在多头仓位 + exit_long=true或者long方向的sl,tp,tsl任一触发即可, 才成立, 其他情况忽略
  * 空头离场信号, 需要同bar出现: 存在空头仓位 + exit_short=true或者short方向的sl,tp,tsl任一触发即可, 才成立, 其他情况忽略
  * 多头进场信号, 需要同bar出现: 无任何方向仓位 + enter_long=true + exit_long=false + enter_short=false + exit_short=false, 才成立, 其他情况忽略
  * 空头进场信号, 需要同bar出现: 无任何方向仓位 + enter_long=false + exit_long=false + enter_short=true + exit_short=false, 才成立, 其他情况忽略
  * 由于这个系统是单仓位系统, 所以存在多头仓位, 就等于只有多头仓位

# 信号优先级
  * skip_mask为true, 就算触发
    * 如果有任何方向的仓位,就直接延迟离场(open[i+1])
    * 即使没有仓位也算触发, 依然要跳过后续信号
  * skip_mask(最高) = atr的止盈止损点有nan跳过 > 反手信号 > 离场信号 > 进场信号
  * 触发了一个信号, 后面的就不触发了, 如触发了skip_mask, 后面3个信号就不触发了, 触发了反手信号, 后面2个信号就不触发了, 触发了离场信号, 后面的进场信号就不触发了

# 离场优先级
  * 如果在同一根bar上出现了多个相同方向的离场信号
    * 在同一根bar上, 出现的不同方向的离场信号, 并不在信号分类里, 会被忽略掉, 所以无需处理
  * sl(当下) > tp(当下) > sl(延迟),tp(延迟),tsl(延迟),exit信号
  * 当下信号, 必然意味着exit_in_bar=true,所以直接取sl,tp计算后的当下止盈止损点位, 作为离场价格
  * 延迟信号,取下一根k线的开盘价, 作为离场价格
  * 如果同一根bar出现了 sl_pct(当下), sl_atr(当下), tp_pct(当下), tp_atr(当下) 其中任意两个以上, 就取最悲观预期(亏的最多的那个,或者赚的最少的那个,止盈止损价)
    *  例如, 当同时配置了sl_pct和sl_atr时,应该两者都计算并取最悲观的那个
    *  例如, 当同时配置了sl_pct和tp_atr时,可以直接取止损, 因为止损更悲观
 *  至于exit_long, exit_short, tsl_long, tsl_short, 因为都是延迟执行, 都是取下一根k线开盘价, 离场价格都是一样的, 所以不存在悲观问题

# 函数返回
  * 函数需要返回, 一个df, 包含列为, 余额数组, 净值数组, 仓位状态, 进场价格, 离场价格, 当前盈亏百分比, 当前离场固定手续费, 当前离场百分比手续费
    * 如果止损参数有效(例如atr_sl>0),就要返回对应的止损数组(代表开仓后的止损价格), 止损参数无效(如atr_sl<=0), 就不返回该列

# 初始化问题
  * 初始状态无仓位
  * 如果atr计算出来的止盈止损点是nan则跳过开仓,(往往是atr前导nan数量), 就直接跳过开仓,优先级等同于skip_mask

# 如何处理最后一根bar
  * 不进行任何特殊处理, 就好像它不是最后一根bar

# 关于手续费问题
  * 手续费只在离场时扣一次, 进场时不用计算手续费
  * 如果是当下k线离场, 就在当下k线扣手续费, 如果是延迟k线离场, 那么就在下一根k线时扣手续费
  * 反手有两种情况, 也是同样的道理
  * 一种反手情况是,如果是反手进场前平仓(当下k线), 在下一根k线开盘价进场, 最后是反手离场
    * 这种情况, 反手进场前平仓(当下k线)时扣一次手续费, 然后在反手离场时扣一次手续费
  * 另一种反手情况是,如果是反手进场前平仓(延迟k线),在下一根k线开盘价进场
    * 这种情况, 反手进场前平仓(延迟k线)时扣一次手续费, 然后在反手离场时扣一次手续费
  ## 滑点问题
    * 不需要考虑滑点, 滑点已经包含在手续费里了, 要求用户自己提高手续费, 进行悲观估算包含滑点价差网络波动在内的总手续费, 这个问题交给用户设置

# 计算盈亏的方式
1. 无需计算具体盈亏金额, 而是计算价格盈亏百分比, 然后乘以下单金额, 得出盈亏
2. 这个回测引擎默认是没有杠杆的, 相当于永久1倍杠杆

# 为什么没有杠杆
1. 因为可以在回测后用( 1/最大回测*安全系数(0.8)=可承受最大杠杆)
2. 也就是杠杆配置交给用户层去处理, 所以回测引擎不设置杠杆, 而是单纯验证策略有效性

# 仓位管理的计算方式
1. 从历史最高帐户净值开始, 如果下跌百分比超过, stop_pct, 停止开仓直到取消限制, (并不需要触发离场, 不影响已有仓位, 只是停止新的开仓)
2. 从历史最高帐户净值开始, 到当前bar之间, 找到最低点, 如果相对于最低点恢复超过了resume_pct, 取消开仓限制, (并不是立即开仓, 依然要等到有开仓信号, 才开仓)


@/src/data_conversion/input/data_dict.rs
@/src/data_conversion/input/param_set.rs

BacktestParams 我目前参数根本不够, 得先增加参数, 然后再进行主循环的设计


关于atr的计算, 在循环前调用 atr_eager 一次性计算就行了

 src/backtest_engine/indicators/atr.rs:126-128
```
/// **计算层 (Eager Wrapper)**
pub fn atr_eager(ohlcv_df: &DataFrame, config: &ATRConfig) -> Result<Series, QuantError> {
    let period = config.period;
```

注意atr函数的参数, 要用new方法, 因为有默认值
src/backtest_engine/indicators/atr.rs:8-30
```
;

/// ATR (Average True Range) 的配置结构体
pub struct ATRConfig {
    pub period: i64,
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub alias_name: String,
}

impl ATRConfig {
    pub fn new(period: i64) -> Self {
        ATRConfig {
            period,
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            alias_name: "atr".to_string(),
        }
    }
}

```

注意Param的使用, 访问param.value, 其他属性的都是用来优化的, 跟本次任务无关
@/src/data_conversion/input/param.rs


用来回测的ohlcv, 这样获取, processed_data.source["ohlcv"] 如果key不存在直接报错就行了
ohlcv有 time, open, high, low, close, volume, 列名不存在报错就行了
src/data_conversion/input/data_dict.rs:5-13
```

#[derive(Clone)]
pub struct DataContainer {
    pub mapping: DataFrame,
    pub skip_mask: Series,
    pub skip_mapping: HashMap<String, bool>,
    pub source: HashMap<String, Vec<DataFrame>>,
}

```

不要用unsafe, 一点微小的性能损失可以接受

关于异常类:
参考 @/src/error
需要为这个回测模块设计一个异常子类, 放在 src/error 文件夹

关于性能问题
1. 到底是深拷贝好, 还是找零拷贝下的高性能循环方式好, 这个回测引擎是单线程硬件环境下运行的, 涉及大量密集型
2. 最佳实践是用contig_slice, 性能高, 先检测数据是否连续, 不连续直接报错, 让用户在外面处理好再传进来

文件放到src/backtest_engine/backtester文件夹下面, 并且需要把文件拆分成合适的大小, 提高可维护性

给我一套详细完整的方案, 等我确认后, 和我充分讨论后, 再更新代码

把方案拆分成细粒度
把大文件拆分成多个小文件
把大任务拆分成小任务
调用子任务Code处理
每次子任务只实现一个小任务, 只处理一个文件
告诉子任务, 忽略过程中的编译报错, 优先执行任务
