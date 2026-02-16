/// RSI 配置结构体。
pub struct RSIConfig {
    pub period: i64,
    pub column_name: String,
    pub alias_name: String,
}

impl RSIConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "rsi".to_string(),
        }
    }
}
