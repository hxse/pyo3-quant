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
pub use action::Action;
pub use backtest_state::BacktestState;
pub use capital_state::CapitalState;
pub use current_bar_data::CurrentBarData;
pub use position_state::Position;
pub use risk_trigger::risk_state::RiskState;
