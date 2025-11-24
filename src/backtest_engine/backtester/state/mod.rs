// 导出所有子模块
pub mod action;
pub mod backtest_state;
pub mod capital_calculator;
pub mod capital_state;
pub mod current_bar_data;
pub mod position_calculator;
pub mod position_state;
pub mod risk_trigger;

// 重新导出主要类型，方便外部使用
pub use {
    action::Action, backtest_state::BacktestState, capital_state::CapitalState,
    current_bar_data::CurrentBarData, position_state::Position,
    risk_trigger::risk_state::RiskState,
};
