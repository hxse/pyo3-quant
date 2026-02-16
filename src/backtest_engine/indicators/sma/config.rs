/// 简单移动平均线 (SMA) 的配置结构体。
pub struct SMAConfig {
    pub period: i64,
    pub column_name: String,
    pub alias_name: String,
}

impl SMAConfig {
    /// 创建 SMA 配置，默认输入列为 close。
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "sma".to_string(),
        }
    }
}
