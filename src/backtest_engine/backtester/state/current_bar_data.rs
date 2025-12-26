use crate::backtest_engine::backtester::data_preparer::PreparedData;

/// 当前 bar 的数据封装结构体
///
/// 用于封装单个时间点的所有市场数据，避免重复传递多个参数
#[derive(Debug, Clone, Copy, Default)]
pub struct CurrentBarData {
    /// 开盘价
    pub open: f64,
    /// 最高价
    pub high: f64,
    /// 最低价
    pub low: f64,
    /// 收盘价
    pub close: f64,
    /// 进多信号
    pub entry_long: bool,
    /// 出多信号
    pub exit_long: bool,
    /// 进空信号
    pub entry_short: bool,
    /// 出空信号
    pub exit_short: bool,
    /// ATR 值（如果存在）
    pub atr: Option<f64>,
}

impl CurrentBarData {
    /// 从原始值创建 CurrentBarData（用于迭代器，无边界检查）
    #[inline]
    pub fn from_values(
        open: f64,
        high: f64,
        low: f64,
        close: f64,
        entry_long: i32,
        exit_long: i32,
        entry_short: i32,
        exit_short: i32,
        atr: Option<f64>,
    ) -> Self {
        Self {
            open,
            high,
            low,
            close,
            entry_long: entry_long != 0,
            exit_long: exit_long != 0,
            entry_short: entry_short != 0,
            exit_short: exit_short != 0,
            atr,
        }
    }

    /// 从 PreparedData 和索引创建（保留用于初始化）
    #[inline]
    pub fn new(prepared_data: &PreparedData, index: usize) -> Self {
        Self::from_values(
            prepared_data.open[index],
            prepared_data.high[index],
            prepared_data.low[index],
            prepared_data.close[index],
            prepared_data.entry_long[index],
            prepared_data.exit_long[index],
            prepared_data.entry_short[index],
            prepared_data.exit_short[index],
            prepared_data.atr.as_ref().map(|v| v[index]),
        )
    }
}
