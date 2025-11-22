use crate::backtest_engine::backtester::state::BacktestState;

/// 打印当前仓位状态调试信息
pub fn print_position_debug(state: &BacktestState, index: usize) {
    println!("=== Position State Debug Info (Index {}) ===", index);

    // Position info
    println!("current_position: {:?}", state.action.current_position);
    println!("previous_position: {:?}", state.action.previous_position);

    // Price info - always show all prices, even if None
    println!("entry_long_price: {:?}", state.action.entry_long_price);
    println!("entry_short_price: {:?}", state.action.entry_short_price);
    println!("exit_long_price: {:?}", state.action.exit_long_price);
    println!("exit_short_price: {:?}", state.action.exit_short_price);

    // Risk trigger info
    println!("risk_long_trigger: {}", state.action.risk_long_trigger);
    println!("risk_short_trigger: {}", state.action.risk_short_trigger);
    println!("risk_in_bar: {}", state.action.risk_in_bar);
    println!(
        "previous_risk_in_bar: {}",
        state.action.previous_risk_in_bar
    );

    // Current bar data
    println!(
        "current_bar - open: {:.4}, high: {:.4}, low: {:.4}, close: {:.4}, volume: {}",
        state.current_bar.open,
        state.current_bar.high,
        state.current_bar.low,
        state.current_bar.close,
        state.current_bar.volume
    );
    println!("atr: {:?}", state.current_bar.atr);

    // Signal info
    println!(
        "signals - enter_long: {}, enter_short: {}, exit_long: {}, exit_short: {}",
        state.current_bar.enter_long,
        state.current_bar.enter_short,
        state.current_bar.exit_long,
        state.current_bar.exit_short
    );

    // Capital state
    println!(
        "capital - balance: {:.2}, equity: {:.2}, fee: {:.2}",
        state.capital_state.balance, state.capital_state.equity, state.capital_state.fee
    );
    println!(
        "returns - trade_pnl_pct: {:.2}%, total_return_pct: {:.2}%",
        state.capital_state.trade_pnl_pct, state.capital_state.total_return_pct
    );

    // Decision conditions
    println!("decisions:");
    println!("  should_enter_long: {}", state.should_enter_long());
    println!("  should_enter_short: {}", state.should_enter_short());
    println!("  should_exit_long: {}", state.should_exit_long());
    println!("  should_exit_short: {}", state.should_exit_short());
    println!(
        "  should_reverse_to_long: {}",
        state.should_reverse_to_long()
    );
    println!(
        "  should_reverse_to_short: {}",
        state.should_reverse_to_short()
    );

    println!("==========================================");
}
