// 导出所有子模块
pub mod backtest_state;
pub mod current_bar_data;
pub mod exit_conditions;
pub mod position;
pub mod position_calculator;

// 重新导出主要类型，方便外部使用
pub use backtest_state::BacktestState;
pub use current_bar_data::CurrentBarData;
pub use position::Position;
