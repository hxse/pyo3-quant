use std::f64;

/// PSAR 方向枚举（用于初始化时强制方向）
#[derive(Debug, Clone, Copy)]
pub(crate) enum ForceDirection {
    Auto,  // 自动判断方向
    Long,  // 强制多头
    Short, // 强制空头
}

// 核心状态结构体
#[derive(Debug, Clone, Copy)]
pub struct PsarState {
    pub(crate) is_long: bool,     // true=多头, false=空头
    pub(crate) current_psar: f64, // 当前PSAR值
    pub(crate) current_ep: f64,   // 当前极端点 (Extreme Point)
    pub(crate) current_af: f64,   // 当前加速因子 (Acceleration Factor)
}

// 2. 初始化函数：移植psar_init
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
            // 自动判断
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

// 3. 第一次迭代函数：移植psar_first_iteration
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
    // 计算next_psar_raw_candidate
    // 2. 计算next_psar_raw_candidate
    let next_psar_raw_candidate = if state.is_long {
        state.current_psar + state.current_af * (state.current_ep - state.current_psar)
    } else {
        state.current_psar - state.current_af * (state.current_psar - state.current_ep)
    };

    // 3. 穿透检查（使用前一根K线数据）
    state.current_psar = if state.is_long {
        next_psar_raw_candidate.min(low_prev)
    } else {
        next_psar_raw_candidate.max(high_prev)
    };

    // 4. 判断反转（使用当前K线数据与next_psar_raw_candidate比较）
    let reversal = if state.is_long {
        low_curr < next_psar_raw_candidate // ✓ 使用next_psar_raw_candidate
    } else {
        high_curr > next_psar_raw_candidate // ✓ 使用next_psar_raw_candidate
    };

    // 5. 更新EP和AF（在反转判断之前，且不管是否反转都要执行）
    if state.is_long {
        if high_curr > state.current_ep {
            state.current_ep = high_curr;
            state.current_af = (state.current_af + af_step).min(max_af);
        }
    } else if low_curr < state.current_ep {
        state.current_ep = low_curr;
        state.current_af = (state.current_af + af_step).min(max_af);
    }

    // 6. 处理反转（如果发生）
    if reversal {
        reversal_val = 1.0;
        state.is_long = !state.is_long;
        state.current_af = af0;
        state.current_psar = state.current_ep; // 使用更新后的EP
        if state.is_long {
            state.current_psar = state.current_psar.min(low_curr);
            state.current_ep = high_curr;
        } else {
            state.current_psar = state.current_psar.max(high_curr);
            state.current_ep = low_curr;
        }
    }

    // 7. 设置返回值
    if state.is_long {
        psar_long_val = state.current_psar;
    } else {
        psar_short_val = state.current_psar;
    }

    (state, psar_long_val, psar_short_val, reversal_val)
}

// 4. 更新函数：移植psar_update
pub(crate) fn psar_update(
    prev_state: &PsarState,
    current_high: f64,
    current_low: f64,
    prev_high: f64,
    prev_low: f64,
    af_step: f64,
    max_af: f64,
    force_direction: Option<ForceDirection>, // 强制方向 (None=允许反转, Some=强制方向)
) -> (PsarState, f64, f64, f64) {
    let mut new_state = *prev_state; // 复制前一个状态
    let mut psar_long_val = f64::NAN;
    let mut psar_short_val = f64::NAN;
    let mut reversal_val = 0.0;
    // 1. 计算原始PSAR候选值
    let next_psar_raw_candidate = if new_state.is_long {
        new_state.current_psar
            + new_state.current_af * (new_state.current_ep - new_state.current_psar)
    } else {
        new_state.current_psar
            - new_state.current_af * (new_state.current_psar - new_state.current_ep)
    };

    // 2. 应用穿透规则（使用prev K线）
    new_state.current_psar = if new_state.is_long {
        next_psar_raw_candidate.min(prev_low)
    } else {
        next_psar_raw_candidate.max(prev_high)
    };

    // 3. 判断是否发生反转（仅当未强制方向时）
    let reversal = if force_direction.is_none() {
        // 未强制方向时才检查反转
        if new_state.is_long {
            current_low < next_psar_raw_candidate
        } else {
            current_high > next_psar_raw_candidate
        }
    } else {
        false // 强制方向时不反转
    };

    // 4. 更新EP和AF（在反转判断之前，且不管是否反转都要执行）
    if new_state.is_long {
        if current_high > new_state.current_ep {
            new_state.current_ep = current_high;
            new_state.current_af = (new_state.current_af + af_step).min(max_af);
        }
    } else if current_low < new_state.current_ep {
        new_state.current_ep = current_low;
        new_state.current_af = (new_state.current_af + af_step).min(max_af);
    }

    // 5. 处理反转（如果发生）
    if reversal {
        reversal_val = 1.0;
        new_state.is_long = !new_state.is_long;
        new_state.current_af = af_step;
        new_state.current_psar = prev_state.current_ep; // 反转后PSAR设置为前一根K线的EP
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

// 1. 核心计算函数：直接移植numba逻辑
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
    // 初始化结果向量
    let mut psar_long = vec![f64::NAN; n];
    let mut psar_short = vec![f64::NAN; n];
    let mut psar_af = vec![f64::NAN; n];
    let mut psar_reversal = vec![0.0; n];
    // 边界检查
    if n < 2 {
        return (psar_long, psar_short, psar_af, psar_reversal);
    }

    // 索引0：只初始化af和reversal
    psar_af[0] = af0;
    psar_reversal[0] = 0.0;
    // psar_long[0]和psar_short[0]保持NaN

    // 索引1：调用psar_first_iteration计算（有实际值）
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

    // 如果第一次迭代返回NaN，直接返回
    if state.current_psar.is_nan() {
        return (psar_long, psar_short, psar_af, psar_reversal);
    }

    // 从索引2开始的主循环
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
            None, // 允许反转（指标用途）
        );
        psar_long[i] = long_val;
        psar_short[i] = short_val;
        psar_af[i] = new_state.current_af;
        psar_reversal[i] = rev_val;
        current_state = new_state;
    }
    (psar_long, psar_short, psar_af, psar_reversal)
}
