/// 收盘价相对 SMA 百分比配置。
pub struct SmaClosePctConfig {
    pub period: i64,
    pub alias_name: String,
}

impl SmaClosePctConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            alias_name: "sma_close_pct".to_string(),
        }
    }
}
