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

    #[error("No data in container")]
    NoData,

    #[error("No optimizable parameters found")]
    NoOptimizableParams,

    #[error("Walk-forward window generation failed: {0}")]
    WindowGenerationFailed(String),
}
