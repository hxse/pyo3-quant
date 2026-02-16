use std::f64;

/// PSAR 方向枚举（用于初始化时强制方向）。
#[derive(Debug, Clone, Copy)]
pub(crate) enum ForceDirection {
    Auto,
    Long,
    Short,
}

/// PSAR 核心状态。
#[derive(Debug, Clone, Copy)]
pub struct PsarState {
    pub(crate) is_long: bool,
    pub(crate) current_psar: f64,
    pub(crate) current_ep: f64,
    pub(crate) current_af: f64,
}

/// 初始化状态。
pub(crate) fn psar_init(
    high_prev: f64,
    high_curr: f64,
    low_prev: f64,
    low_curr: f64,
    close_prev: f64,
    force_direction: ForceDirection,
    af0: f64,
) -> PsarState {
    let is_long = match force_direction {
        ForceDirection::Long => true,
        ForceDirection::Short => false,
        ForceDirection::Auto => {
            let up_dm = high_curr - high_prev;
            let dn_dm = low_prev - low_curr;
            let is_falling_initial = dn_dm > up_dm && dn_dm > 0.0;
            !is_falling_initial
        }
    };

    let current_psar = close_prev;
    let current_ep = if is_long { high_prev } else { low_prev };
    let current_af = af0;
    PsarState {
        is_long,
        current_psar,
        current_ep,
        current_af,
    }
}

/// 第一次迭代。
pub(crate) fn psar_first_iteration(
    high_prev: f64,
    high_curr: f64,
    low_prev: f64,
    low_curr: f64,
    close_prev: f64,
    force_direction: ForceDirection,
    af0: f64,
    af_step: f64,
    max_af: f64,
) -> (PsarState, f64, f64, f64) {
    let mut state = psar_init(
        high_prev,
        high_curr,
        low_prev,
        low_curr,
        close_prev,
        force_direction,
        af0,
    );
    let mut psar_long_val = f64::NAN;
    let mut psar_short_val = f64::NAN;
    let mut reversal_val = 0.0;

    let next_psar_raw_candidate = if state.is_long {
        state.current_psar + state.current_af * (state.current_ep - state.current_psar)
    } else {
        state.current_psar - state.current_af * (state.current_psar - state.current_ep)
    };

    state.current_psar = if state.is_long {
        next_psar_raw_candidate.min(low_prev)
    } else {
        next_psar_raw_candidate.max(high_prev)
    };

    let reversal = if state.is_long {
        low_curr < next_psar_raw_candidate
    } else {
        high_curr > next_psar_raw_candidate
    };

    if state.is_long {
        if high_curr > state.current_ep {
            state.current_ep = high_curr;
            state.current_af = (state.current_af + af_step).min(max_af);
        }
    } else if low_curr < state.current_ep {
        state.current_ep = low_curr;
        state.current_af = (state.current_af + af_step).min(max_af);
    }

    if reversal {
        reversal_val = 1.0;
        state.is_long = !state.is_long;
        state.current_af = af0;
        state.current_psar = state.current_ep;
        if state.is_long {
            state.current_psar = state.current_psar.min(low_curr);
            state.current_ep = high_curr;
        } else {
            state.current_psar = state.current_psar.max(high_curr);
            state.current_ep = low_curr;
        }
    }

    if state.is_long {
        psar_long_val = state.current_psar;
    } else {
        psar_short_val = state.current_psar;
    }

    (state, psar_long_val, psar_short_val, reversal_val)
}

/// 常规迭代更新。
pub(crate) fn psar_update(
    prev_state: &PsarState,
    current_high: f64,
    current_low: f64,
    prev_high: f64,
    prev_low: f64,
    af_step: f64,
    max_af: f64,
    force_direction: Option<ForceDirection>,
) -> (PsarState, f64, f64, f64) {
    let mut new_state = *prev_state;
    let mut psar_long_val = f64::NAN;
    let mut psar_short_val = f64::NAN;
    let mut reversal_val = 0.0;

    let next_psar_raw_candidate = if new_state.is_long {
        new_state.current_psar + new_state.current_af * (new_state.current_ep - new_state.current_psar)
    } else {
        new_state.current_psar - new_state.current_af * (new_state.current_psar - new_state.current_ep)
    };

    new_state.current_psar = if new_state.is_long {
        next_psar_raw_candidate.min(prev_low)
    } else {
        next_psar_raw_candidate.max(prev_high)
    };

    let reversal = if force_direction.is_none() {
        if new_state.is_long {
            current_low < next_psar_raw_candidate
        } else {
            current_high > next_psar_raw_candidate
        }
    } else {
        false
    };

    if new_state.is_long {
        if current_high > new_state.current_ep {
            new_state.current_ep = current_high;
            new_state.current_af = (new_state.current_af + af_step).min(max_af);
        }
    } else if current_low < new_state.current_ep {
        new_state.current_ep = current_low;
        new_state.current_af = (new_state.current_af + af_step).min(max_af);
    }

    if reversal {
        reversal_val = 1.0;
        new_state.is_long = !new_state.is_long;
        new_state.current_af = af_step;
        new_state.current_psar = prev_state.current_ep;
        if new_state.is_long {
            new_state.current_psar = new_state.current_psar.min(current_low);
            new_state.current_ep = current_high;
        } else {
            new_state.current_psar = new_state.current_psar.max(current_high);
            new_state.current_ep = current_low;
        }
    }

    if new_state.is_long {
        psar_long_val = new_state.current_psar;
    } else {
        psar_short_val = new_state.current_psar;
    }
    (new_state, psar_long_val, psar_short_val, reversal_val)
}
