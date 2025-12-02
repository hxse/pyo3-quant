use crate::backtest_engine::backtester::state::BacktestState;

/// 打印当前仓位状态调试信息（价格驱动版本）
pub fn print_position_debug(state: &BacktestState, index: usize) {
    println!("=== Position State Debug Info (Index {}) ===", index);

    // 价格列（价格驱动状态核心）
    println!("entry_long_price: {:?}", state.action.entry_long_price);
    println!("entry_short_price: {:?}", state.action.entry_short_price);
    println!("exit_long_price: {:?}", state.action.exit_long_price);
    println!("exit_short_price: {:?}", state.action.exit_short_price);

    // Risk状态机
    let risk_in_bar_value = if state.risk_state.should_exit_in_bar_long() {
        1
    } else if state.risk_state.should_exit_in_bar_short() {
        -1
    } else {
        0
    };
    println!(
        "risk_in_bar: {} (0=next_bar, 1=long_risk, -1=short_risk)",
        risk_in_bar_value
    );

    // 推断状态（基于价格）
    println!("inferred_state: {}", state.debug_inferred_state());

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
        state.capital_state.trade_pnl_pct * 100.0,
        state.capital_state.total_return_pct * 100.0
    );

    // 状态判断辅助函数
    println!("state_checks:");
    println!("  has_no_position: {}", state.has_no_position());
    println!("  has_long_position: {}", state.has_long_position());
    println!("  has_short_position: {}", state.has_short_position());
    println!("  is_exiting_long: {}", state.is_exiting_long());
    println!("  is_exiting_short: {}", state.is_exiting_short());
    println!("  can_enter_long: {}", state.can_enter_long());
    println!("  can_enter_short: {}", state.can_enter_short());

    println!("==========================================");
}
