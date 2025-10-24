use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

#[derive(Clone)]
pub struct DataContainer {
    pub mapping: DataFrame,
    pub skip_mask: DataFrame,
    pub source: HashMap<String, Vec<DataFrame>>,
}

impl<'py> FromPyObject<'py> for DataContainer {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let mapping_py: PyDataFrame = ob.getattr("mapping")?.extract()?;
        let skip_mask_py: PyDataFrame = ob.getattr("skip_mask")?.extract()?;
        let source_py: HashMap<String, Vec<PyDataFrame>> = ob.getattr("source")?.extract()?;

        Ok(DataContainer {
            mapping: mapping_py.into(),
            skip_mask: skip_mask_py.into(),
            source: source_py
                .into_iter()
                .map(|(k, v)| (k, v.into_iter().map(|df| df.into()).collect()))
                .collect(),
        })
    }
}
