use pyo3::prelude::*;

#[derive(Debug, Clone, FromPyObject)]
#[pyo3(from_item_all)]
pub struct Param {
    pub value: f64,
    pub initial_value: f64,
    pub min: f64,
    pub initial_min: f64,
    pub max: f64,
    pub initial_max: f64,
    pub step: f64,
    pub initial_step: f64,
}
