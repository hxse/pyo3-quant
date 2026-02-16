/// 通用背离检测配置
pub struct DivergenceConfig {
    pub window: usize,
    pub gap: i32,
    pub recency: i32,
    pub indicator_col: String,
}

impl DivergenceConfig {
    pub fn new(window: usize, indicator_col: &str) -> Self {
        Self {
            window,
            gap: 3,
            recency: 3,
            indicator_col: indicator_col.to_string(),
        }
    }
}
