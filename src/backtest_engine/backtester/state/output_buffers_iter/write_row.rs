use crate::backtest_engine::backtester::output::OutputBuffers;
use crate::backtest_engine::backtester::state::BacktestState;

use super::super::write_config::WriteConfig;

impl OutputBuffers {
    /// 按索引写入单行数据（统一写入接口）。
    /// 用于初始化阶段（row 0/1）的随机访问写入。
    #[inline]
    pub fn write_row(&mut self, i: usize, state: &BacktestState<'_>, config: &WriteConfig) {
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
        self.frame_state[i] = state.frame_state as u8;

        if !config.pct_funcs.is_empty() {
            if config.pct_funcs.has_sl {
                if let (Some(long_values), Some(short_values)) = (
                    self.sl_pct_price_long.as_mut(),
                    self.sl_pct_price_short.as_mut(),
                ) {
                    long_values[i] = state.risk_state.sl_pct_price_long.unwrap_or(f64::NAN);
                    short_values[i] = state.risk_state.sl_pct_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.pct_funcs.has_tp {
                if let (Some(long_values), Some(short_values)) = (
                    self.tp_pct_price_long.as_mut(),
                    self.tp_pct_price_short.as_mut(),
                ) {
                    long_values[i] = state.risk_state.tp_pct_price_long.unwrap_or(f64::NAN);
                    short_values[i] = state.risk_state.tp_pct_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.pct_funcs.has_tsl {
                if let (Some(long_values), Some(short_values)) = (
                    self.tsl_pct_price_long.as_mut(),
                    self.tsl_pct_price_short.as_mut(),
                ) {
                    long_values[i] = state.risk_state.tsl_pct_price_long.unwrap_or(f64::NAN);
                    short_values[i] = state.risk_state.tsl_pct_price_short.unwrap_or(f64::NAN);
                }
            }
        }

        if !config.atr_funcs.is_empty() {
            if config.atr_funcs.has_sl {
                if let (Some(long_values), Some(short_values)) = (
                    self.sl_atr_price_long.as_mut(),
                    self.sl_atr_price_short.as_mut(),
                ) {
                    long_values[i] = state.risk_state.sl_atr_price_long.unwrap_or(f64::NAN);
                    short_values[i] = state.risk_state.sl_atr_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.atr_funcs.has_tp {
                if let (Some(long_values), Some(short_values)) = (
                    self.tp_atr_price_long.as_mut(),
                    self.tp_atr_price_short.as_mut(),
                ) {
                    long_values[i] = state.risk_state.tp_atr_price_long.unwrap_or(f64::NAN);
                    short_values[i] = state.risk_state.tp_atr_price_short.unwrap_or(f64::NAN);
                }
            }
            if config.atr_funcs.has_tsl {
                if let (Some(long_values), Some(short_values)) = (
                    self.tsl_atr_price_long.as_mut(),
                    self.tsl_atr_price_short.as_mut(),
                ) {
                    long_values[i] = state.risk_state.tsl_atr_price_long.unwrap_or(f64::NAN);
                    short_values[i] = state.risk_state.tsl_atr_price_short.unwrap_or(f64::NAN);
                }
            }
        }

        if config.has_psar {
            if let (Some(long_values), Some(short_values)) = (
                self.tsl_psar_price_long.as_mut(),
                self.tsl_psar_price_short.as_mut(),
            ) {
                long_values[i] = state.risk_state.tsl_psar_price_long.unwrap_or(f64::NAN);
                short_values[i] = state.risk_state.tsl_psar_price_short.unwrap_or(f64::NAN);
            }
        }

        if let Some(atr_values) = self.atr.as_mut() {
            atr_values[i] = state.current_bar.atr.unwrap_or(f64::NAN);
        }
    }
}
