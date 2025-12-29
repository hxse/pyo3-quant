//! TSL PSAR 模块 - 使用 Parabolic SAR 作为跟踪止损

use super::Direction;
use crate::backtest_engine::indicators::psar::psar_core::{
    psar_init, psar_update, ForceDirection, PsarState,
};

/// PSAR 止损配置参数
pub struct TslPsarParams {
    pub af0: f64,     // 初始加速因子 (默认 0.02)
    pub af_step: f64, // 加速因子步进 (默认 0.02)
    pub max_af: f64,  // 最大加速因子 (默认 0.2)
}

/// 初始化 PSAR 止损状态
///
/// # 参数
/// * `prev_prev_high` - 开仓前两根 K 线（bar[i-2]）的最高价
/// * `prev_prev_low` - 开仓前两根 K 线（bar[i-2]）的最低价
/// * `prev_prev_close` - 开仓前两根 K 线（bar[i-2]）的收盘价
/// * `prev_high` - 开仓前一根 K 线（bar[i-1]）的最高价
/// * `prev_low` - 开仓前一根 K 线（bar[i-1]）的最低价
/// * `prev_close` - 开仓前一根 K 线（bar[i-1]）的收盘价
/// * `direction` - 持仓方向
/// * `params` - PSAR 参数配置
/// * `anchor_mode` - 锚点模式（true=使用High/Low, false=使用Close）
///
/// # 返回
/// * `(PsarState, f64)` - PSAR 状态和当前K线（bar[i]）的止损价格
pub fn init_tsl_psar(
    prev_prev_high: f64,
    prev_prev_low: f64,
    prev_prev_close: f64,
    prev_high: f64,
    prev_low: f64,
    prev_close: f64,
    direction: Direction,
    params: &TslPsarParams,
    anchor_mode: bool,
) -> (PsarState, f64) {
    let force_dir = match direction {
        Direction::Long => ForceDirection::Long,
        Direction::Short => ForceDirection::Short,
    };

    // 根据 anchor_mode 决定使用 High/Low 还是 Close
    // 当 anchor_mode=false 时，将所有 High/Low 替换为 Close
    // 这样 PSAR 计算逻辑（包括 EP 更新和穿透规则）都会基于收盘价，避免 High/Low 毛刺的影响
    let (pp_h, pp_l, p_h, p_l) = if anchor_mode {
        (prev_prev_high, prev_prev_low, prev_high, prev_low)
    } else {
        (prev_prev_close, prev_prev_close, prev_close, prev_close)
    };

    // 1. 用 psar_init 初始化状态（不含反转逻辑）
    // 注意：psar_init 主要确定初始 EP。如果 anchor_mode=false，初始 EP 也应该是 Close。
    let init_state = psar_init(pp_h, p_h, pp_l, p_l, prev_prev_close, force_dir, params.af0);

    // 2. 用 psar_update 计算第一次更新（强制方向不反转）
    let (updated_state, _psar_long, _psar_short, _) = psar_update(
        &init_state,
        p_h,
        p_l,
        pp_h,
        pp_l,
        params.af_step,
        params.max_af,
        Some(force_dir), // 强制方向，不允许反转
    );

    // 3. 直接使用 current_psar（无论反转与否都有正确值）
    (updated_state, updated_state.current_psar)
}

/// 更新 PSAR 止损状态
///
/// # 参数
/// * `prev_state` - 上一根 K 线的 PSAR 状态
/// * `curr_high` - 当前 K 线的最高价
/// * `curr_low` - 当前 K 线的最低价
/// * `curr_close` - 当前 K 线的收盘价
/// * `prev_high` - 前一根 K 线的最高价
/// * `prev_low` - 前一根 K 线的最低价
/// * `prev_close` - 前一根 K 线的收盘价
/// * `direction` - 持仓方向
/// * `params` - PSAR 参数配置
/// * `anchor_mode` - 锚点模式（true=使用High/Low, false=使用Close）
///
/// # 返回
/// * `(PsarState, f64)` - 新的 PSAR 状态和止损价格
pub fn update_tsl_psar(
    prev_state: &PsarState,
    curr_high: f64,
    curr_low: f64,
    curr_close: f64,
    prev_high: f64,
    prev_low: f64,
    prev_close: f64,
    direction: Direction,
    params: &TslPsarParams,
    anchor_mode: bool,
) -> (PsarState, f64) {
    let force_dir = match direction {
        Direction::Long => ForceDirection::Long,
        Direction::Short => ForceDirection::Short,
    };

    // 根据 anchor_mode 决定使用 High/Low 还是 Close
    let (c_h, c_l, p_h, p_l) = if anchor_mode {
        (curr_high, curr_low, prev_high, prev_low)
    } else {
        (curr_close, curr_close, prev_close, prev_close)
    };

    let (new_state, psar_long, psar_short, _) = psar_update(
        prev_state,
        c_h,
        c_l,
        p_h,
        p_l,
        params.af_step,
        params.max_af,
        Some(force_dir), // 强制方向，不允许反转
    );

    // 忽略 PSAR 的自然反转，强制使用当前持仓方向的值
    let psar_price = match direction {
        Direction::Long => {
            if new_state.is_long {
                psar_long
            } else {
                psar_short
            }
        }
        Direction::Short => {
            if !new_state.is_long {
                psar_short
            } else {
                psar_long
            }
        }
    };

    (new_state, psar_price)
}
