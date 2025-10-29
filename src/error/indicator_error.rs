use thiserror::Error;

#[derive(Error, Debug)]
pub enum IndicatorError {
    #[error("Parameter '{0}' not found for indicator '{1}'")]
    ParameterNotFound(String, String),

    #[error("Invalid parameter for '{0}': {1}")]
    InvalidParameter(String, String),

    #[error("Input column '{0}' not found")]
    ColumnNotFound(String),
    
    #[error("Input data is too short to calculate indicator '{0}' with period '{1}'")]
    DataTooShort(String, i64),
}
