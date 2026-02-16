/// 布林带配置结构体。
pub struct BBandsConfig {
    pub period: i64,
    pub std_multiplier: f64,
    pub close_col: String,
    pub middle_band_alias: String,
    pub std_dev_alias: String,
    pub upper_band_alias: String,
    pub lower_band_alias: String,
    pub bandwidth_alias: String,
    pub percent_alias: String,
}

impl BBandsConfig {
    pub fn new(period: i64, std_multiplier: f64) -> Self {
        Self {
            period,
            std_multiplier,
            close_col: "close".to_string(),
            middle_band_alias: "middle_band".to_string(),
            std_dev_alias: "std_dev".to_string(),
            upper_band_alias: "upper_band".to_string(),
            lower_band_alias: "lower_band".to_string(),
            bandwidth_alias: "bandwidth".to_string(),
            percent_alias: "percent".to_string(),
        }
    }
}
