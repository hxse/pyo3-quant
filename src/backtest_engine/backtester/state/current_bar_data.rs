use crate::backtest_engine::backtester::data_preparer::PreparedData;

/// 当前 bar 的数据封装结构体
///
/// 用于封装单个时间点的所有市场数据，避免重复传递多个参数
pub struct CurrentBarData {
    /// 时间戳
    pub time: i64,
    /// 开盘价
    pub open: f64,
    /// 最高价
    pub high: f64,
    /// 最低价
    pub low: f64,
    /// 收盘价
    pub close: f64,
    /// 成交量
    pub volume: f64,
    /// 进多信号
    pub enter_long: bool,
    /// 出多信号
    pub exit_long: bool,
    /// 进空信号
    pub enter_short: bool,
    /// 出空信号
    pub exit_short: bool,
    /// ATR 值（如果存在）
    pub atr: Option<f64>,
}

impl CurrentBarData {
    /// 从 PreparedData 和索引创建当前 bar 数据
    ///
    /// # 参数
    /// * `prepared_data` - 准备好的数据
    /// * `index` - 当前索引
    ///
    pub fn default() -> Self {
        Self {
            time: 0,
            open: 0.0,
            high: 0.0,
            low: 0.0,
            close: 0.0,
            volume: 0.0,
            enter_long: false,
            exit_long: false,
            enter_short: false,
            exit_short: false,
            atr: None,
        }
    }

    /// 创建新的当前 bar 数据
    pub fn new(prepared_data: &PreparedData, index: usize) -> Self {
        Self {
            time: prepared_data.time[index],
            open: prepared_data.open[index],
            high: prepared_data.high[index],
            low: prepared_data.low[index],
            close: prepared_data.close[index],
            volume: prepared_data.volume[index],
            enter_long: prepared_data.enter_long[index] != 0,
            exit_long: prepared_data.exit_long[index] != 0,
            enter_short: prepared_data.enter_short[index] != 0,
            exit_short: prepared_data.exit_short[index] != 0,
            atr: prepared_data.atr.as_ref().map(|atr_vec| atr_vec[index]),
        }
    }
}
