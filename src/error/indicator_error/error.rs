use thiserror::Error;

#[derive(Error, Debug)]
pub enum IndicatorError {
    #[error("Parameter '{0}' not found for indicator '{1}'")]
    ParameterNotFound(String, String),

    #[error("Invalid parameter for '{0}': {1}")]
    InvalidParameter(String, String),

    #[error("Input column '{0}' not found")]
    ColumnNotFound(String),

    #[error(
        "Input data is too short to calculate indicator '{0}' with period '{1}' data count '{2}'"
    )]
    DataTooShort(String, i64, i64),

    #[error("Indicator '{0}' is not implemented or supported.")]
    NotImplemented(String),

    #[error("Data source '{0}' not found")]
    DataSourceNotFound(String),

    #[error("Data source '{0}' length ({1}) does not match indicator parameters length ({2})")]
    DataSourceLengthMismatch(String, usize, usize),
}
