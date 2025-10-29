use super::indicator_error::IndicatorError;
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

    // 将 SignalError 作为子错误集成进来
    #[error("Signal generation error: {0}")]
    Signal(#[from] SignalError),

    // 将 IndicatorError 作为子错误集成进来
    #[error("Indicator error: {0}")]
    Indicator(#[from] IndicatorError),

    #[error("Infrastructure error: {0}")]
    InfrastructureError(String),
}
