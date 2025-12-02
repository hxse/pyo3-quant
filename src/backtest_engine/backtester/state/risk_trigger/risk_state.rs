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

    /// 多头 risk 触发价格（如果触发）
    pub exit_long_price: Option<f64>,
    /// 空头 risk 触发价格（如果触发）
    pub exit_short_price: Option<f64>,
    /// 是否在当前 bar 内触发（true=in_bar, false=next_bar）
    pub exit_in_bar: bool,
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

            exit_long_price: None,
            exit_short_price: None,
            exit_in_bar: false,
        }
    }
}

impl RiskState {
    /// 重置 risk 触发状态
    pub fn reset_exit_state(&mut self) {
        self.exit_long_price = None;
        self.exit_short_price = None;
        self.exit_in_bar = false;
    }

    /// 判断多头是否在 in_bar 模式触发
    pub fn should_exit_in_bar_long(&self) -> bool {
        self.exit_long_price.is_some() && self.exit_in_bar
    }

    /// 判断空头是否在 in_bar 模式触发
    pub fn should_exit_in_bar_short(&self) -> bool {
        self.exit_short_price.is_some() && self.exit_in_bar
    }

    /// 判断多头是否在 next_bar 模式触发
    pub fn should_exit_next_bar_long(&self) -> bool {
        self.exit_long_price.is_some() && !self.exit_in_bar
    }

    /// 判断空头是否在 next_bar 模式触发
    pub fn should_exit_next_bar_short(&self) -> bool {
        self.exit_short_price.is_some() && !self.exit_in_bar
    }
}
