/// ⚙️ Configuration for the ADX indicator.
#[derive(Debug, Clone, PartialEq)]
pub struct ADXConfig {
    /// ⏳ Period for ADX calculation.
    pub period: i64,
    /// ⏳ Period for ADXR calculation.
    pub adxr_length: i64,
    /// 📈 High column name.
    pub high_col: String,
    /// 📉 Low column name.
    pub low_col: String,
    /// 📊 Close column name.
    pub close_col: String,
    /// 🏷 Alias for the ADX output column.
    pub adx_alias: String,
    /// 🏷 Alias for the Plus DM output column.
    pub plus_dm_alias: String,
    /// 🏷 Alias for the Minus DM output column.
    pub minus_dm_alias: String,
    /// 🏷 Alias for the ADXR output column.
    pub adxr_alias: String,
}

impl ADXConfig {
    pub fn new(period: i64, adxr_length: i64) -> Self {
        Self {
            period,
            adxr_length,
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            adx_alias: "adx".to_string(),
            plus_dm_alias: "plus_dm".to_string(),
            minus_dm_alias: "minus_dm".to_string(),
            adxr_alias: "adxr".to_string(),
        }
    }
}
