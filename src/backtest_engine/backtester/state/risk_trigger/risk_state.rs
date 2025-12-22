use crate::backtest_engine::indicators::psar::psar_core::PsarState;

#[derive(Debug, Clone)]
pub struct RiskState {
    // === 百分比风险价格（多空分离） ===
    pub sl_pct_price_long: Option<f64>,
    pub sl_pct_price_short: Option<f64>,
    pub tp_pct_price_long: Option<f64>,
    pub tp_pct_price_short: Option<f64>,
    pub tsl_pct_price_long: Option<f64>,
    pub tsl_pct_price_short: Option<f64>,

    // === ATR 风险价格（多空分离） ===
    pub sl_atr_price_long: Option<f64>,
    pub sl_atr_price_short: Option<f64>,
    pub tp_atr_price_long: Option<f64>,
    pub tp_atr_price_short: Option<f64>,
    pub tsl_atr_price_long: Option<f64>,
    pub tsl_atr_price_short: Option<f64>,

    /// 当前持仓期间最高价（用于跟踪止损计算）
    pub highest_since_entry: Option<f64>,
    /// 当前持仓期间最低价（用于跟踪止损计算）
    pub lowest_since_entry: Option<f64>,

    // === PSAR 跟踪止损状态（多空分离） ===
    pub tsl_psar_state_long: Option<PsarState>,
    pub tsl_psar_state_short: Option<PsarState>,
    pub tsl_psar_price_long: Option<f64>,
    pub tsl_psar_price_short: Option<f64>,

    /// 多头 risk 触发价格（如果触发）
    pub exit_long_price: Option<f64>,
    /// 空头 risk 触发价格（如果触发）
    pub exit_short_price: Option<f64>,
    /// 风控触发方向：0=无/next_bar, 1=多头in_bar, -1=空头in_bar
    pub in_bar_direction: i8,
}

impl Default for RiskState {
    fn default() -> Self {
        Self {
            sl_pct_price_long: None,
            sl_pct_price_short: None,
            tp_pct_price_long: None,
            tp_pct_price_short: None,
            tsl_pct_price_long: None,
            tsl_pct_price_short: None,

            sl_atr_price_long: None,
            sl_atr_price_short: None,
            tp_atr_price_long: None,
            tp_atr_price_short: None,
            tsl_atr_price_long: None,
            tsl_atr_price_short: None,

            highest_since_entry: None,
            lowest_since_entry: None,

            tsl_psar_state_long: None,
            tsl_psar_state_short: None,
            tsl_psar_price_long: None,
            tsl_psar_price_short: None,

            exit_long_price: None,
            exit_short_price: None,
            in_bar_direction: 0,
        }
    }
}

impl RiskState {
    /// 重置 risk 触发状态（每次风险检查前调用）
    ///
    /// 只重置触发相关字段，保留风险价格阈值（持仓期间需要保持）
    pub fn reset_exit_state(&mut self) {
        self.exit_long_price = None;
        self.exit_short_price = None;
        self.in_bar_direction = 0;
    }

    /// 重置所有状态（跳过 bar 时调用）
    ///
    /// 完全清空所有风险相关状态
    pub fn reset_all(&mut self) {
        *self = Self::default();
    }

    /// 重置多头风险状态（多头离场后调用）
    ///
    /// 清除多头方向的所有风险价格和极值追踪
    pub fn reset_long_state(&mut self) {
        self.sl_pct_price_long = None;
        self.tp_pct_price_long = None;
        self.tsl_pct_price_long = None;
        self.sl_atr_price_long = None;
        self.tp_atr_price_long = None;
        self.tsl_atr_price_long = None;
        self.highest_since_entry = None;
        self.tsl_psar_state_long = None;
        self.tsl_psar_price_long = None;
        self.exit_long_price = None;
    }

    /// 重置空头风险状态（空头离场后调用）
    ///
    /// 清除空头方向的所有风险价格和极值追踪
    pub fn reset_short_state(&mut self) {
        self.sl_pct_price_short = None;
        self.tp_pct_price_short = None;
        self.tsl_pct_price_short = None;
        self.sl_atr_price_short = None;
        self.tp_atr_price_short = None;
        self.tsl_atr_price_short = None;
        self.lowest_since_entry = None;
        self.tsl_psar_state_short = None;
        self.tsl_psar_price_short = None;
        self.exit_short_price = None;
    }

    /// 判断多头是否在 in_bar 模式触发
    pub fn should_exit_in_bar_long(&self) -> bool {
        self.exit_long_price.is_some() && self.in_bar_direction == 1
    }

    /// 判断空头是否在 in_bar 模式触发
    pub fn should_exit_in_bar_short(&self) -> bool {
        self.exit_short_price.is_some() && self.in_bar_direction == -1
    }

    /// 判断多头是否在 next_bar 模式触发
    pub fn should_exit_next_bar_long(&self) -> bool {
        self.exit_long_price.is_some() && self.in_bar_direction != 1
    }

    /// 判断空头是否在 next_bar 模式触发
    pub fn should_exit_next_bar_short(&self) -> bool {
        self.exit_short_price.is_some() && self.in_bar_direction != -1
    }
}
