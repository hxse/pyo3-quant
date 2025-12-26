use super::{output::OutputBuffers, state::BacktestState};

/// 固定列切片集合
pub struct FixedSlices<'a> {
    balance: &'a mut [f64],
    equity: &'a mut [f64],
    trade_pnl_pct: &'a mut [f64],
    total_return_pct: &'a mut [f64],
    fee: &'a mut [f64],
    fee_cum: &'a mut [f64],
    current_drawdown: &'a mut [f64],
    entry_long_price: &'a mut [f64],
    entry_short_price: &'a mut [f64],
    exit_long_price: &'a mut [f64],
    exit_short_price: &'a mut [f64],
    risk_in_bar_direction: &'a mut [i8],
    first_entry_side: &'a mut [i8],
}

/// 可选列切片集合
pub struct OptionalSlices<'a> {
    sl_pct_long: Option<&'a mut [f64]>,
    sl_pct_short: Option<&'a mut [f64]>,
    tp_pct_long: Option<&'a mut [f64]>,
    tp_pct_short: Option<&'a mut [f64]>,
    tsl_pct_long: Option<&'a mut [f64]>,
    tsl_pct_short: Option<&'a mut [f64]>,
    sl_atr_long: Option<&'a mut [f64]>,
    sl_atr_short: Option<&'a mut [f64]>,
    tp_atr_long: Option<&'a mut [f64]>,
    tp_atr_short: Option<&'a mut [f64]>,
    tsl_atr_long: Option<&'a mut [f64]>,
    tsl_atr_short: Option<&'a mut [f64]>,
    tsl_psar_long: Option<&'a mut [f64]>,
    tsl_psar_short: Option<&'a mut [f64]>,
}

impl<'a> FixedSlices<'a> {
    /// 写入固定列数据到指定索引
    #[inline(always)]
    pub fn write(&mut self, state: &BacktestState, i: usize) {
        self.balance[i] = state.capital_state.balance;
        self.equity[i] = state.capital_state.equity;
        self.trade_pnl_pct[i] = state.capital_state.trade_pnl_pct;
        self.total_return_pct[i] = state.capital_state.total_return_pct;
        self.fee[i] = state.capital_state.fee;
        self.fee_cum[i] = state.capital_state.fee_cum;
        self.current_drawdown[i] = state.capital_state.current_drawdown;
        self.entry_long_price[i] = state.action.entry_long_price.unwrap_or(f64::NAN);
        self.entry_short_price[i] = state.action.entry_short_price.unwrap_or(f64::NAN);
        self.exit_long_price[i] = state.action.exit_long_price.unwrap_or(f64::NAN);
        self.exit_short_price[i] = state.action.exit_short_price.unwrap_or(f64::NAN);
        self.risk_in_bar_direction[i] = state.risk_state.in_bar_direction;
        self.first_entry_side[i] = state.action.first_entry_side;
    }
}

impl<'a> OptionalSlices<'a> {
    /// 写入可选列数据到指定索引
    #[inline(always)]
    pub fn write(&mut self, state: &BacktestState, i: usize) {
        if let Some(v) = self.sl_pct_long.as_mut() {
            v[i] = state.risk_state.sl_pct_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.sl_pct_short.as_mut() {
            v[i] = state.risk_state.sl_pct_price_short.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tp_pct_long.as_mut() {
            v[i] = state.risk_state.tp_pct_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tp_pct_short.as_mut() {
            v[i] = state.risk_state.tp_pct_price_short.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tsl_pct_long.as_mut() {
            v[i] = state.risk_state.tsl_pct_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tsl_pct_short.as_mut() {
            v[i] = state.risk_state.tsl_pct_price_short.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.sl_atr_long.as_mut() {
            v[i] = state.risk_state.sl_atr_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.sl_atr_short.as_mut() {
            v[i] = state.risk_state.sl_atr_price_short.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tp_atr_long.as_mut() {
            v[i] = state.risk_state.tp_atr_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tp_atr_short.as_mut() {
            v[i] = state.risk_state.tp_atr_price_short.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tsl_atr_long.as_mut() {
            v[i] = state.risk_state.tsl_atr_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tsl_atr_short.as_mut() {
            v[i] = state.risk_state.tsl_atr_price_short.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tsl_psar_long.as_mut() {
            v[i] = state.risk_state.tsl_psar_price_long.unwrap_or(f64::NAN);
        }
        if let Some(v) = self.tsl_psar_short.as_mut() {
            v[i] = state.risk_state.tsl_psar_price_short.unwrap_or(f64::NAN);
        }
    }
}

/// 从 OutputBuffers 同时提取固定列和可选列切片
/// 这样做可以避免多次可变借用 buffers 导致的借用检查错误
#[inline]
pub fn extract_slices(buffers: &mut OutputBuffers) -> (FixedSlices<'_>, OptionalSlices<'_>) {
    let fixed = FixedSlices {
        balance: &mut buffers.balance,
        equity: &mut buffers.equity,
        trade_pnl_pct: &mut buffers.trade_pnl_pct,
        total_return_pct: &mut buffers.total_return_pct,
        fee: &mut buffers.fee,
        fee_cum: &mut buffers.fee_cum,
        current_drawdown: &mut buffers.current_drawdown,
        entry_long_price: &mut buffers.entry_long_price,
        entry_short_price: &mut buffers.entry_short_price,
        exit_long_price: &mut buffers.exit_long_price,
        exit_short_price: &mut buffers.exit_short_price,
        risk_in_bar_direction: &mut buffers.risk_in_bar_direction,
        first_entry_side: &mut buffers.first_entry_side,
    };

    let opt = OptionalSlices {
        sl_pct_long: buffers.sl_pct_price_long.as_deref_mut(),
        sl_pct_short: buffers.sl_pct_price_short.as_deref_mut(),
        tp_pct_long: buffers.tp_pct_price_long.as_deref_mut(),
        tp_pct_short: buffers.tp_pct_price_short.as_deref_mut(),
        tsl_pct_long: buffers.tsl_pct_price_long.as_deref_mut(),
        tsl_pct_short: buffers.tsl_pct_price_short.as_deref_mut(),
        sl_atr_long: buffers.sl_atr_price_long.as_deref_mut(),
        sl_atr_short: buffers.sl_atr_price_short.as_deref_mut(),
        tp_atr_long: buffers.tp_atr_price_long.as_deref_mut(),
        tp_atr_short: buffers.tp_atr_price_short.as_deref_mut(),
        tsl_atr_long: buffers.tsl_atr_price_long.as_deref_mut(),
        tsl_atr_short: buffers.tsl_atr_price_short.as_deref_mut(),
        tsl_psar_long: buffers.tsl_psar_price_long.as_deref_mut(),
        tsl_psar_short: buffers.tsl_psar_price_short.as_deref_mut(),
    };

    (fixed, opt)
}
