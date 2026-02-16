use crate::backtest_engine::backtester::state::BacktestState;

use super::super::write_config::WriteConfig;

/// 输出缓冲区行数据结构体。
/// 包含当前行所有输出列的可变引用。
pub struct OutputRow<'a> {
    // 固定列
    pub balance: &'a mut f64,
    pub equity: &'a mut f64,
    pub trade_pnl_pct: &'a mut f64,
    pub total_return_pct: &'a mut f64,
    pub fee: &'a mut f64,
    pub fee_cum: &'a mut f64,
    pub current_drawdown: &'a mut f64,
    pub entry_long_price: &'a mut f64,
    pub entry_short_price: &'a mut f64,
    pub exit_long_price: &'a mut f64,
    pub exit_short_price: &'a mut f64,
    pub risk_in_bar_direction: &'a mut i8,
    pub first_entry_side: &'a mut i8,
    pub frame_state: &'a mut u8,
    // 可选列
    pub sl_pct_long: Option<&'a mut f64>,
    pub sl_pct_short: Option<&'a mut f64>,
    pub tp_pct_long: Option<&'a mut f64>,
    pub tp_pct_short: Option<&'a mut f64>,
    pub tsl_pct_long: Option<&'a mut f64>,
    pub tsl_pct_short: Option<&'a mut f64>,
    pub sl_atr_long: Option<&'a mut f64>,
    pub sl_atr_short: Option<&'a mut f64>,
    pub tp_atr_long: Option<&'a mut f64>,
    pub tp_atr_short: Option<&'a mut f64>,
    pub tsl_atr_long: Option<&'a mut f64>,
    pub tsl_atr_short: Option<&'a mut f64>,
    pub tsl_psar_long: Option<&'a mut f64>,
    pub tsl_psar_short: Option<&'a mut f64>,
}

impl<'a> OutputRow<'a> {
    /// 写入固定列数据。
    #[inline]
    fn write_fixed(&mut self, state: &BacktestState<'_>) {
        *self.balance = state.capital_state.balance;
        *self.equity = state.capital_state.equity;
        *self.trade_pnl_pct = state.capital_state.trade_pnl_pct;
        *self.total_return_pct = state.capital_state.total_return_pct;
        *self.fee = state.capital_state.fee;
        *self.fee_cum = state.capital_state.fee_cum;
        *self.current_drawdown = state.capital_state.current_drawdown;
        *self.entry_long_price = state.action.entry_long_price.unwrap_or(f64::NAN);
        *self.entry_short_price = state.action.entry_short_price.unwrap_or(f64::NAN);
        *self.exit_long_price = state.action.exit_long_price.unwrap_or(f64::NAN);
        *self.exit_short_price = state.action.exit_short_price.unwrap_or(f64::NAN);
        *self.risk_in_bar_direction = state.risk_state.in_bar_direction;
        *self.first_entry_side = state.action.first_entry_side;
        *self.frame_state = state.frame_state as u8;
    }

    /// 按组写入可选列数据。
    /// 使用 WriteConfig 按类型组(PCT/ATR/PSAR)和功能组(SL/TP/TSL)分层检查。
    #[inline]
    fn write_optional_grouped(&mut self, state: &BacktestState<'_>, config: &WriteConfig) {
        if !config.pct_funcs.is_empty() {
            if config.pct_funcs.has_sl {
                **self.sl_pct_long.as_mut().unwrap() =
                    state.risk_state.sl_pct_price_long.unwrap_or(f64::NAN);
                **self.sl_pct_short.as_mut().unwrap() =
                    state.risk_state.sl_pct_price_short.unwrap_or(f64::NAN);
            }
            if config.pct_funcs.has_tp {
                **self.tp_pct_long.as_mut().unwrap() =
                    state.risk_state.tp_pct_price_long.unwrap_or(f64::NAN);
                **self.tp_pct_short.as_mut().unwrap() =
                    state.risk_state.tp_pct_price_short.unwrap_or(f64::NAN);
            }
            if config.pct_funcs.has_tsl {
                **self.tsl_pct_long.as_mut().unwrap() =
                    state.risk_state.tsl_pct_price_long.unwrap_or(f64::NAN);
                **self.tsl_pct_short.as_mut().unwrap() =
                    state.risk_state.tsl_pct_price_short.unwrap_or(f64::NAN);
            }
        }

        if !config.atr_funcs.is_empty() {
            if config.atr_funcs.has_sl {
                **self.sl_atr_long.as_mut().unwrap() =
                    state.risk_state.sl_atr_price_long.unwrap_or(f64::NAN);
                **self.sl_atr_short.as_mut().unwrap() =
                    state.risk_state.sl_atr_price_short.unwrap_or(f64::NAN);
            }
            if config.atr_funcs.has_tp {
                **self.tp_atr_long.as_mut().unwrap() =
                    state.risk_state.tp_atr_price_long.unwrap_or(f64::NAN);
                **self.tp_atr_short.as_mut().unwrap() =
                    state.risk_state.tp_atr_price_short.unwrap_or(f64::NAN);
            }
            if config.atr_funcs.has_tsl {
                **self.tsl_atr_long.as_mut().unwrap() =
                    state.risk_state.tsl_atr_price_long.unwrap_or(f64::NAN);
                **self.tsl_atr_short.as_mut().unwrap() =
                    state.risk_state.tsl_atr_price_short.unwrap_or(f64::NAN);
            }
        }

        if config.has_psar {
            **self.tsl_psar_long.as_mut().unwrap() =
                state.risk_state.tsl_psar_price_long.unwrap_or(f64::NAN);
            **self.tsl_psar_short.as_mut().unwrap() =
                state.risk_state.tsl_psar_price_short.unwrap_or(f64::NAN);
        }
    }

    /// 从 BacktestState 写入数据到当前行（分组优化版本）。
    #[inline]
    pub fn write(&mut self, state: &BacktestState<'_>, config: &WriteConfig) {
        self.write_fixed(state);
        self.write_optional_grouped(state, config);
    }
}
