/// MACD 的配置結構體
pub struct MACDConfig {
    pub fast_period: i64,      // 快速周期
    pub slow_period: i64,      // 慢速周期
    pub signal_period: i64,    // 信號周期
    pub column_name: String,   // 輸入列名
    pub fast_ema_name: String, // 快速 EMA 臨時列名
    pub slow_ema_name: String, // 慢速 EMA 臨時列名
    pub macd_alias: String,    // MACD 輸出別名
    pub signal_alias: String,  // Signal 輸出別名
    pub hist_alias: String,    // Histogram 輸出別名
}

impl MACDConfig {
    pub fn new(fast_period: i64, slow_period: i64, signal_period: i64) -> Self {
        Self {
            fast_period,
            slow_period,
            signal_period,
            column_name: "close".to_string(),
            fast_ema_name: "fast_ema".to_string(),
            slow_ema_name: "slow_ema".to_string(),
            macd_alias: "macd".to_string(),
            signal_alias: "signal".to_string(),
            hist_alias: "hist".to_string(),
        }
    }
}
