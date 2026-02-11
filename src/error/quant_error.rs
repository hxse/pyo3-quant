use super::backtest_error::BacktestError;
use super::indicator_error::IndicatorError;
use super::optimizer_error::OptimizerError;
use super::signal_error::SignalError;
use polars::prelude::PolarsError;
use pyo3::PyErr;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum QuantError {
    #[error("Polars error: {0}")]
    Polars(#[from] PolarsError),

    #[error("PyO3 error: {0}")]
    PyO3(#[from] PyErr),

    #[error("Signal generation error: {0}")]
    Signal(#[from] SignalError),

    #[error("Indicator error: {0}")]
    Indicator(#[from] IndicatorError),

    #[error("Backtest error: {0}")]
    Backtest(#[from] BacktestError),

    #[error("Optimizer error: {0}")]
    Optimizer(#[from] OptimizerError),

    #[error("Infrastructure error: {0}")]
    InfrastructureError(String),

    #[error("Invalid parameter: {0}")]
    InvalidParam(String),
}
