use super::risk_price_calc::Direction;
use crate::backtest_engine::indicators::psar::psar_core::PsarState;

#[derive(Debug, Clone, Default)]
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

    /// 多头锚点（用于跟踪止损计算，根据 tsl_anchor_mode 可能是 close 或 high）
    pub long_anchor_since_entry: Option<f64>,
    /// 空头锚点（用于跟踪止损计算，根据 tsl_anchor_mode 可能是 close 或 low）
    pub short_anchor_since_entry: Option<f64>,

    // === PSAR 跟踪止损状态（多空分离） ===
    pub tsl_psar_state_long: Option<PsarState>,
    pub tsl_psar_state_short: Option<PsarState>,
    pub tsl_psar_price_long: Option<f64>,
    pub tsl_psar_price_short: Option<f64>,

    /// 多头 risk 触发价格（如果触发）
    pub risk_long_price: Option<f64>,
    /// 空头 risk 触发价格（如果触发）
    pub risk_short_price: Option<f64>,
    /// 风控触发方向：0=无/next_bar, 1=多头in_bar, -1=空头in_bar
    pub in_bar_direction: i8,
}

impl RiskState {
    // --- 辅助访问方法 (按方向) ---

    pub fn sl_pct_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.sl_pct_price_long,
            Direction::Short => self.sl_pct_price_short,
        }
    }
    pub fn set_sl_pct_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.sl_pct_price_long = val,
            Direction::Short => self.sl_pct_price_short = val,
        }
    }

    pub fn tp_pct_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.tp_pct_price_long,
            Direction::Short => self.tp_pct_price_short,
        }
    }
    pub fn set_tp_pct_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.tp_pct_price_long = val,
            Direction::Short => self.tp_pct_price_short = val,
        }
    }

    pub fn sl_atr_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.sl_atr_price_long,
            Direction::Short => self.sl_atr_price_short,
        }
    }
    pub fn set_sl_atr_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.sl_atr_price_long = val,
            Direction::Short => self.sl_atr_price_short = val,
        }
    }

    pub fn tp_atr_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.tp_atr_price_long,
            Direction::Short => self.tp_atr_price_short,
        }
    }
    pub fn set_tp_atr_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.tp_atr_price_long = val,
            Direction::Short => self.tp_atr_price_short = val,
        }
    }

    pub fn tsl_pct_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.tsl_pct_price_long,
            Direction::Short => self.tsl_pct_price_short,
        }
    }
    pub fn set_tsl_pct_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.tsl_pct_price_long = val,
            Direction::Short => self.tsl_pct_price_short = val,
        }
    }

    pub fn tsl_atr_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.tsl_atr_price_long,
            Direction::Short => self.tsl_atr_price_short,
        }
    }
    pub fn set_tsl_atr_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.tsl_atr_price_long = val,
            Direction::Short => self.tsl_atr_price_short = val,
        }
    }

    pub fn tsl_psar_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.tsl_psar_price_long,
            Direction::Short => self.tsl_psar_price_short,
        }
    }
    pub fn set_tsl_psar_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.tsl_psar_price_long = val,
            Direction::Short => self.tsl_psar_price_short = val,
        }
    }

    pub fn anchor_since_entry(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.long_anchor_since_entry,
            Direction::Short => self.short_anchor_since_entry,
        }
    }
    pub fn set_anchor_since_entry(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.long_anchor_since_entry = val,
            Direction::Short => self.short_anchor_since_entry = val,
        }
    }

    pub fn tsl_psar_state(&self, dir: Direction) -> &Option<PsarState> {
        match dir {
            Direction::Long => &self.tsl_psar_state_long,
            Direction::Short => &self.tsl_psar_state_short,
        }
    }
    pub fn set_tsl_psar_state(&mut self, dir: Direction, val: Option<PsarState>) {
        match dir {
            Direction::Long => self.tsl_psar_state_long = val,
            Direction::Short => self.tsl_psar_state_short = val,
        }
    }

    pub fn exit_price(&self, dir: Direction) -> Option<f64> {
        match dir {
            Direction::Long => self.risk_long_price,
            Direction::Short => self.risk_short_price,
        }
    }
    pub fn set_exit_price(&mut self, dir: Direction, val: Option<f64>) {
        match dir {
            Direction::Long => self.risk_long_price = val,
            Direction::Short => self.risk_short_price = val,
        }
    }

    /// 重置 risk 触发状态（每次风险检查前调用）
    ///
    /// 只重置触发相关字段，保留风险价格阈值（持仓期间需要保持）
    pub fn reset_exit_state(&mut self) {
        self.risk_long_price = None;
        self.risk_short_price = None;
        self.in_bar_direction = 0;
    }

    /// 重置所有风险状态（资金归零跳过时使用）
    pub fn reset_all(&mut self) {
        self.reset_long_state();
        self.reset_short_state();
        self.reset_exit_state();
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
        self.long_anchor_since_entry = None;
        self.tsl_psar_state_long = None;
        self.tsl_psar_price_long = None;
        self.risk_long_price = None;
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
        self.short_anchor_since_entry = None;
        self.tsl_psar_state_short = None;
        self.tsl_psar_price_short = None;
        self.risk_short_price = None;
    }

    /// 判断多头是否在 in_bar 模式触发
    pub fn should_exit_in_bar_long(&self) -> bool {
        self.risk_long_price.is_some() && self.in_bar_direction == 1
    }

    /// 判断空头是否在 in_bar 模式触发
    pub fn should_exit_in_bar_short(&self) -> bool {
        self.risk_short_price.is_some() && self.in_bar_direction == -1
    }

    /// 判断多头是否在 next_bar 模式触发
    pub fn should_exit_next_bar_long(&self) -> bool {
        self.risk_long_price.is_some() && self.in_bar_direction != 1
    }

    /// 判断空头是否在 next_bar 模式触发
    pub fn should_exit_next_bar_short(&self) -> bool {
        self.risk_short_price.is_some() && self.in_bar_direction != -1
    }
}
