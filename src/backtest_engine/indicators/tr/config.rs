/// 真实波幅 (TR) 的配置结构体。
pub struct TRConfig {
    pub high_col: String,
    pub low_col: String,
    pub close_col: String,
    pub alias_name: String,
}

impl TRConfig {
    pub fn new() -> Self {
        Self {
            high_col: "high".to_string(),
            low_col: "low".to_string(),
            close_col: "close".to_string(),
            alias_name: "tr".to_string(),
        }
    }
}
