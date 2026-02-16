/// PSAR 指标配置。
pub struct PSARConfig {
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub af0: f64,
    pub af_step: f64,
    pub max_af: f64,
    // 输出列名
    pub psar_long_alias: String,
    pub psar_short_alias: String,
    pub psar_af_alias: String,
    pub psar_reversal_alias: String,
}

impl PSARConfig {
    pub fn new(af0: f64, af_step: f64, max_af: f64) -> Self {
        PSARConfig {
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            af0,
            af_step,
            max_af,
            psar_long_alias: "psar_long".to_string(),
            psar_short_alias: "psar_short".to_string(),
            psar_af_alias: "psar_af".to_string(),
            psar_reversal_alias: "psar_reversal".to_string(),
        }
    }
}
