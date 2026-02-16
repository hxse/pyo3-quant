use std::f64;

use super::state::{psar_first_iteration, psar_update, ForceDirection};

/// 核心计算函数：直接移植 numba 逻辑。
#[allow(dead_code)]
pub(crate) fn calc_psar_core(
    high: &[f64],
    low: &[f64],
    close: &[f64],
    af0: f64,
    af_step: f64,
    max_af: f64,
) -> (Vec<f64>, Vec<f64>, Vec<f64>, Vec<f64>) {
    let n = high.len();
    let mut psar_long = vec![f64::NAN; n];
    let mut psar_short = vec![f64::NAN; n];
    let mut psar_af = vec![f64::NAN; n];
    let mut psar_reversal = vec![0.0; n];

    if n < 2 {
        return (psar_long, psar_short, psar_af, psar_reversal);
    }

    psar_af[0] = af0;
    psar_reversal[0] = 0.0;

    let (state, long_val, short_val, rev_val) = psar_first_iteration(
        high[0],
        high[1],
        low[0],
        low[1],
        close[0],
        ForceDirection::Auto,
        af0,
        af_step,
        max_af,
    );
    psar_long[1] = long_val;
    psar_short[1] = short_val;
    psar_af[1] = state.current_af;
    psar_reversal[1] = rev_val;

    if state.current_psar.is_nan() {
        return (psar_long, psar_short, psar_af, psar_reversal);
    }

    let mut current_state = state;
    for i in 2..n {
        let (new_state, long_val, short_val, rev_val) = psar_update(
            &current_state,
            high[i],
            low[i],
            high[i - 1],
            low[i - 1],
            af_step,
            max_af,
            None,
        );
        psar_long[i] = long_val;
        psar_short[i] = short_val;
        psar_af[i] = new_state.current_af;
        psar_reversal[i] = rev_val;
        current_state = new_state;
    }

    (psar_long, psar_short, psar_af, psar_reversal)
}
