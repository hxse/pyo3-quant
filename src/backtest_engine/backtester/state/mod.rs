// 导出所有子模块
pub mod action;
pub mod backtest_state;
pub mod capital_calculator;
pub mod capital_state;
pub mod current_bar_data;
pub mod frame_events;
pub mod output_buffers_iter;
pub mod position_calculator;
pub mod prepared_data_iter;
pub mod risk_trigger;
pub mod write_config;

// 重新导出主要类型，方便外部使用
pub use backtest_state::BacktestState;
pub use output_buffers_iter::OutputBuffersIter;
pub use prepared_data_iter::PreparedDataIter;
pub use write_config::WriteConfig;
