/// ATR 配置结构体。
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
