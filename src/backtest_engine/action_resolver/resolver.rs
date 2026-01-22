use super::types::{SignalAction, SignalState};
use std::collections::HashMap;

pub struct ResolverParams {
    pub symbol: String,
    pub sl_exit_in_bar: bool,
    pub tp_exit_in_bar: bool,
}

pub fn resolve_actions(row: &HashMap<String, Option<f64>>, params: &ResolverParams) -> SignalState {
    let mut actions: Vec<SignalAction> = Vec::new();
    let mut has_exit = false;
    let symbol = &params.symbol;

    let first_entry_side = get_i8(row, "first_entry_side");
    let entry_long_price = get_f64(row, "entry_long_price");
    let entry_short_price = get_f64(row, "entry_short_price");
    let exit_long_price = get_f64(row, "exit_long_price");
    let exit_short_price = get_f64(row, "exit_short_price");
    let risk_in_bar_direction = get_i8(row, "risk_in_bar_direction");

    // 反手检测
    let is_reversal_l_to_s =
        exit_long_price.is_some() && entry_short_price.is_some() && first_entry_side == -1;
    let is_reversal_s_to_l =
        exit_short_price.is_some() && entry_long_price.is_some() && first_entry_side == 1;

    if is_reversal_l_to_s {
        has_exit = true;
        actions.push(SignalAction::new("close_position", symbol, None, None));
        actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
        actions.push(SignalAction::new(
            "create_limit_order",
            symbol,
            Some("short"),
            entry_short_price,
        ));
        add_sl_tp(&mut actions, row, params, "short");
        return SignalState::new(actions, has_exit);
    }

    if is_reversal_s_to_l {
        has_exit = true;
        actions.push(SignalAction::new("close_position", symbol, None, None));
        actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
        actions.push(SignalAction::new(
            "create_limit_order",
            symbol,
            Some("long"),
            entry_long_price,
        ));
        add_sl_tp(&mut actions, row, params, "long");
        return SignalState::new(actions, has_exit);
    }

    // Next-Bar 离场
    if exit_long_price.is_some() && risk_in_bar_direction == 0 {
        has_exit = true;
        actions.push(SignalAction::new("close_position", symbol, None, None));
        actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
        return SignalState::new(actions, has_exit);
    }
    if exit_short_price.is_some() && risk_in_bar_direction == 0 {
        has_exit = true;
        actions.push(SignalAction::new("close_position", symbol, None, None));
        actions.push(SignalAction::new("cancel_all_orders", symbol, None, None));
        return SignalState::new(actions, has_exit);
    }

    // In-Bar 离场
    if (exit_long_price.is_some() && risk_in_bar_direction == 1)
        || (exit_short_price.is_some() && risk_in_bar_direction == -1)
    {
        return SignalState::new(actions, true);
    }

    // 进场
    if first_entry_side == 1 && entry_long_price.is_some() {
        actions.push(SignalAction::new(
            "create_limit_order",
            symbol,
            Some("long"),
            entry_long_price,
        ));
        add_sl_tp(&mut actions, row, params, "long");
        return SignalState::new(actions, has_exit);
    }
    if first_entry_side == -1 && entry_short_price.is_some() {
        actions.push(SignalAction::new(
            "create_limit_order",
            symbol,
            Some("short"),
            entry_short_price,
        ));
        add_sl_tp(&mut actions, row, params, "short");
        return SignalState::new(actions, has_exit);
    }

    SignalState::new(actions, has_exit)
}

fn add_sl_tp(
    actions: &mut Vec<SignalAction>,
    row: &HashMap<String, Option<f64>>,
    params: &ResolverParams,
    side: &str,
) {
    if params.sl_exit_in_bar {
        let sl = get_f64(row, &format!("sl_atr_price_{}", side))
            .or_else(|| get_f64(row, &format!("sl_pct_price_{}", side)));
        if let Some(price) = sl {
            actions.push(SignalAction::new(
                "create_stop_market_order",
                &params.symbol,
                Some(side),
                Some(price),
            ));
        }
    }
    if params.tp_exit_in_bar {
        let tp = get_f64(row, &format!("tp_atr_price_{}", side))
            .or_else(|| get_f64(row, &format!("tp_pct_price_{}", side)));
        if let Some(price) = tp {
            actions.push(SignalAction::new(
                "create_take_profit_market_order",
                &params.symbol,
                Some(side),
                Some(price),
            ));
        }
    }
}

fn get_f64(row: &HashMap<String, Option<f64>>, key: &str) -> Option<f64> {
    row.get(key).and_then(|v| *v)
}
fn get_i8(row: &HashMap<String, Option<f64>>, key: &str) -> i8 {
    row.get(key).and_then(|v| *v).map(|v| v as i8).unwrap_or(0)
}
