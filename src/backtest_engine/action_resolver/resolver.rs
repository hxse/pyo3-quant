use super::types::{SignalAction, SignalState};
use std::collections::HashMap;

pub struct ResolverParams {
    pub symbol: String,
    pub sl_exit_in_bar: bool,
    pub tp_exit_in_bar: bool,
}

/// 基于 frame_state 解析交易动作。
///
/// 设计约束：
/// - frame_state 仅作为 Bot 侧的高层标签使用，回测引擎内部仍然是价格驱动。
/// - 价格列仅用于提取下单价格与风控价格，不再重复做状态推断。
pub fn resolve_actions(row: &HashMap<String, Option<f64>>, params: &ResolverParams) -> SignalState {
    let mut actions: Vec<SignalAction> = Vec::new();
    let symbol = &params.symbol;
    let frame_state = get_u8(row, "frame_state");

    match frame_state {
        // hold_long_first
        2 => {
            actions.push(SignalAction::new(
                "create_limit_order",
                symbol,
                Some("long"),
                get_f64(row, "entry_long_price"),
            ));
            add_sl_tp(actions.as_mut(), row, params, "long");
            SignalState::new(actions, false)
        }
        // hold_short_first
        4 => {
            actions.push(SignalAction::new(
                "create_limit_order",
                symbol,
                Some("short"),
                get_f64(row, "entry_short_price"),
            ));
            add_sl_tp(actions.as_mut(), row, params, "short");
            SignalState::new(actions, false)
        }
        // exit_long_signal / exit_short_signal
        5 | 8 => {
            actions.push(SignalAction::new("close_position", symbol, None, None));
            actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
            SignalState::new(actions, true)
        }
        // exit_long_risk / exit_long_risk_first / exit_short_risk / exit_short_risk_first
        6 | 7 | 9 | 10 => SignalState::new(actions, true),
        // reversal_S_to_L / reversal_to_L_risk
        12 | 13 => {
            actions.push(SignalAction::new("close_position", symbol, None, None));
            actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
            actions.push(SignalAction::new(
                "create_limit_order",
                symbol,
                Some("long"),
                get_f64(row, "entry_long_price"),
            ));
            add_sl_tp(actions.as_mut(), row, params, "long");
            SignalState::new(actions, true)
        }
        // reversal_L_to_S / reversal_to_S_risk
        11 | 14 => {
            actions.push(SignalAction::new("close_position", symbol, None, None));
            actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
            actions.push(SignalAction::new(
                "create_limit_order",
                symbol,
                Some("short"),
                get_f64(row, "entry_short_price"),
            ));
            add_sl_tp(actions.as_mut(), row, params, "short");
            SignalState::new(actions, true)
        }
        // no_position / hold_long / hold_short / gap_blocked / capital_exhausted / invalid
        _ => SignalState::new(actions, false),
    }
}

fn add_sl_tp(
    actions: &mut Vec<SignalAction>,
    row: &HashMap<String, Option<f64>>,
    params: &ResolverParams,
    side: &str,
) {
    // 同侧风控价格列独立生效：pct 与 atr 可同时挂单。
    if params.sl_exit_in_bar {
        push_if_price(actions, row, &params.symbol, side, "sl_pct_price_", true);
        push_if_price(actions, row, &params.symbol, side, "sl_atr_price_", true);
    }
    if params.tp_exit_in_bar {
        push_if_price(actions, row, &params.symbol, side, "tp_pct_price_", false);
        push_if_price(actions, row, &params.symbol, side, "tp_atr_price_", false);
    }
}

fn get_f64(row: &HashMap<String, Option<f64>>, key: &str) -> Option<f64> {
    row.get(key).and_then(|v| *v)
}
fn get_u8(row: &HashMap<String, Option<f64>>, key: &str) -> u8 {
    row.get(key).and_then(|v| *v).map(|v| v as u8).unwrap_or(0)
}

fn push_if_price(
    actions: &mut Vec<SignalAction>,
    row: &HashMap<String, Option<f64>>,
    symbol: &str,
    side: &str,
    prefix: &str,
    is_stop: bool,
) {
    let key = format!("{}{}", prefix, side);
    if let Some(price) = get_f64(row, &key) {
        let action_type = if is_stop {
            "create_stop_market_order"
        } else {
            "create_take_profit_market_order"
        };
        actions.push(SignalAction::new(
            action_type,
            symbol,
            Some(side),
            Some(price),
        ));
    }
}
