use super::BacktestParams;

impl Default for BacktestParams {
    fn default() -> Self {
        Self {
            sl_pct: None,
            tp_pct: None,
            tsl_pct: None,
            sl_atr: None,
            tp_atr: None,
            tsl_atr: None,
            atr_period: None,
            tsl_psar_af0: None,
            tsl_psar_af_step: None,
            tsl_psar_max_af: None,
            tsl_atr_tight: false,
            sl_exit_in_bar: true,
            tp_exit_in_bar: true,
            sl_trigger_mode: true,
            tp_trigger_mode: true,
            tsl_trigger_mode: true,
            sl_anchor_mode: false,
            tp_anchor_mode: false,
            tsl_anchor_mode: false,
            initial_capital: 10000.0,
            fee_fixed: 0.0,
            fee_pct: 0.0006,
        }
    }
}
