use pyo3::prelude::*;

#[derive(Debug, Clone, FromPyObject)]
pub struct Param {
    pub value: f64,
    pub initial_value: f64,
    pub min: f64,
    pub initial_min: f64,
    pub max: f64,
    pub initial_max: f64,
    pub step: f64,
    pub initial_step: f64,
    pub optimize: bool, // 新增字段
}
