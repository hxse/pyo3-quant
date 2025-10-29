use thiserror::Error;

#[derive(Error, Debug)]
pub enum SignalError {
    #[error("Operand source not found: {0}")]
    SourceNotFound(String),
    #[error("Source index out of bounds: {0}")] // Simplified to a single String
    SourceIndexOutOfBounds(String),
    #[error("Column not found in source: {0}")]
    ColumnNotFound(String),
    #[error("Invalid source format: {0}")]
    InvalidSourceFormat(String),

    #[error("Mapping column '{0}' not found")]
    MappingColumnNotFound(String),
    #[error("Failed to cast mapping index: {0}")]
    MappingCastError(String),
    #[error("Failed to apply mapping to series: {0}")]
    MappingApplyError(String),
    #[error("Parameter '{0}' not found in signal_params")]
    ParameterNotFound(String),
}
