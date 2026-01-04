use crate::types::{BacktestParams, PerformanceMetric, PerformanceParams};

pub fn create_dummy_backtest_params() -> BacktestParams {
    BacktestParams {
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
        sl_exit_in_bar: false,
        tp_exit_in_bar: false,
        sl_trigger_mode: false,
        tp_trigger_mode: false,
        tsl_trigger_mode: false,
        sl_anchor_mode: false,
        tp_anchor_mode: false,
        tsl_anchor_mode: false,
        initial_capital: 10000.0,
        fee_fixed: 0.0,
        fee_pct: 0.0,
    }
}

pub fn create_dummy_performance_params() -> PerformanceParams {
    PerformanceParams {
        metrics: vec![PerformanceMetric::CalmarRatioRaw],
        risk_free_rate: 0.0,
        leverage_safety_factor: None,
    }
}
