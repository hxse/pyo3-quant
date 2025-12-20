use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

pub type DataSource = HashMap<String, DataFrame>;

#[derive(Clone)]
pub struct DataContainer {
    pub mapping: DataFrame,
    pub skip_mask: Option<DataFrame>,
    pub skip_mapping: HashMap<String, bool>,
    pub source: DataSource,
    pub base_data_key: String,
}

impl<'py> FromPyObject<'py> for DataContainer {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let mapping_py: PyDataFrame = ob.getattr("mapping")?.extract()?;
        let skip_mask_py: Option<PyDataFrame> = ob.getattr("skip_mask")?.extract()?;
        let skip_mapping_py: HashMap<String, bool> = ob.getattr("skip_mapping")?.extract()?;
        let source_py: HashMap<String, PyDataFrame> = ob.getattr("source")?.extract()?;
        let base_data_key: String = ob.getattr("BaseDataKey")?.extract()?;

        Ok(DataContainer {
            mapping: mapping_py.into(),
            skip_mask: skip_mask_py.map(|py_df| py_df.into()),
            skip_mapping: skip_mapping_py,
            source: source_py.into_iter().map(|(k, v)| (k, v.into())).collect(),
            base_data_key,
        })
    }
}
