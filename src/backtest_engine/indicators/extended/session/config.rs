/// 开盘 K 线检测配置。
pub struct OpeningBarConfig {
    pub threshold_sec: f64,
    pub alias_name: String,
}

impl OpeningBarConfig {
    pub fn new(threshold_sec: f64) -> Self {
        Self {
            threshold_sec,
            alias_name: "opening_bar".to_string(),
        }
    }

    /// 统一将秒转换为毫秒，避免重复换算逻辑。
    pub fn threshold_ms(&self) -> i64 {
        (self.threshold_sec * 1000.0) as i64
    }
}
