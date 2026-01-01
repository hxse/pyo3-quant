use crate::error::backtest_error::BacktestError;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum OptimizerError {
    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    #[error("Sampling failed: {0}")]
    SamplingFailed(String),

    #[error("Convergence failed: {0}")]
    ConvergenceFailed(String),

    #[error("Backtest error during optimization: {0}")]
    Backtest(#[from] BacktestError),
}
