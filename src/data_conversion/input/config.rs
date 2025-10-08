use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::{Bound, FromPyObject};

#[derive(Debug, Default, FromPyObject)]
pub struct ProcessedConfig {
    pub is_only_performance: bool,
}

pub fn parse(config: Bound<'_, PyDict>) -> PyResult<ProcessedConfig> {
    config.extract().or_else(|_| Ok(ProcessedConfig::default()))
}
