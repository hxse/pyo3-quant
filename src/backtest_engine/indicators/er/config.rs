/// ER (Efficiency Ratio) 配置结构体。
pub struct ERConfig {
    pub length: i64,
    pub drift: i64,
    pub close_col: String,
    pub alias_name: String,
}

impl ERConfig {
    pub fn new(length: i64) -> Self {
        Self {
            length,
            drift: 1,
            close_col: "close".to_string(),
            alias_name: "er".to_string(),
        }
    }
}
