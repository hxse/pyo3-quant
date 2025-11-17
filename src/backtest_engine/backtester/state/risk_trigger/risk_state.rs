#[derive(Debug, Clone)]
pub struct RiskState {
    pub sl_pct_price: Option<f64>,
    pub tp_pct_price: Option<f64>,
    pub tsl_pct_price: Option<f64>,

    pub sl_atr_price: Option<f64>,
    pub tp_atr_price: Option<f64>,
    pub tsl_atr_price: Option<f64>,

    /// 当前持仓期间最高价（用于跟踪止损计算）
    pub highest_since_entry: Option<f64>,
    /// 当前持仓期间最低价（用于跟踪止损计算）
    pub lowest_since_entry: Option<f64>,
}

impl Default for RiskState {
    fn default() -> Self {
        Self {
            sl_pct_price: None,
            tp_pct_price: None,
            tsl_pct_price: None,

            sl_atr_price: None,
            tp_atr_price: None,
            tsl_atr_price: None,

            highest_since_entry: None,
            lowest_since_entry: None,
        }
    }
}
