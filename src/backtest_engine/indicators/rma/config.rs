/// RMA 配置结构体。
pub struct RMAConfig {
    pub period: i64,
    pub column_name: String,
    pub alias_name: String,
}

impl RMAConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "rma".to_string(),
        }
    }
}
