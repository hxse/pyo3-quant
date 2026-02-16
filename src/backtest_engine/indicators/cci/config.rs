/// CCI 配置结构体。
pub struct CCIConfig {
    pub period: i64,
    pub constant: f64,
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub alias_name: String,
}

impl CCIConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            constant: 0.015,
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            alias_name: "cci".to_string(),
        }
    }
}
