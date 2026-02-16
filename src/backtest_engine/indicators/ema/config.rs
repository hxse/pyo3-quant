/// EMA 配置结构体。
pub struct EMAConfig {
    pub period: i64,
    pub column_name: String,
    pub alias_name: String,
    pub processed_column_alias: String,
    pub initial_value_temp: String,
    pub start_offset: i64,
    pub ignore_nulls: bool,
}

impl EMAConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "ema".to_string(),
            processed_column_alias: "ema_processed_close_temp".to_string(),
            initial_value_temp: "ema_initial_value_temp".to_string(),
            start_offset: 0,
            ignore_nulls: true,
        }
    }
}
