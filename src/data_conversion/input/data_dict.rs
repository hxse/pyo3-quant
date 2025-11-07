use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::{PyDataFrame, PySeries};
use std::collections::HashMap;

pub type DataSource = HashMap<String, Vec<DataFrame>>;

#[derive(Clone)]
pub struct DataContainer {
    pub mapping: DataFrame,
    pub skip_mask: Series,
    pub skip_mapping: HashMap<String, bool>,
    pub source: DataSource,
}

impl<'py> FromPyObject<'py> for DataContainer {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let mapping_py: PyDataFrame = ob.getattr("mapping")?.extract()?;
        let skip_mask_py: PySeries = ob.getattr("skip_mask")?.extract()?;
        let skip_mapping_py: HashMap<String, bool> = ob.getattr("skip_mapping")?.extract()?;
        let source_py: HashMap<String, Vec<PyDataFrame>> = ob.getattr("source")?.extract()?;

        Ok(DataContainer {
            mapping: mapping_py.into(),
            skip_mask: skip_mask_py.into(),
            skip_mapping: skip_mapping_py,
            source: source_py
                .into_iter()
                .map(|(k, v)| (k, v.into_iter().map(|df| df.into()).collect()))
                .collect(),
        })
    }
}
