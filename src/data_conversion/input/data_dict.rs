use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

#[derive(Clone)]
pub struct ProcessedDataDict {
    pub mapping: DataFrame,
    pub skip_mask: DataFrame,
    pub ohlcv: Vec<DataFrame>,
    pub extra_data: HashMap<String, Vec<DataFrame>>,
}

impl<'py> FromPyObject<'py> for ProcessedDataDict {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let mapping_py: PyDataFrame = ob.getattr("mapping")?.extract()?;
        let skip_mask_py: PyDataFrame = ob.getattr("skip_mask")?.extract()?;
        let ohlcv_py: Vec<PyDataFrame> = ob.getattr("ohlcv")?.extract()?;
        let extra_data_py: HashMap<String, Vec<PyDataFrame>> =
            ob.getattr("extra_data")?.extract()?;

        Ok(ProcessedDataDict {
            mapping: mapping_py.into(),
            skip_mask: skip_mask_py.into(),
            ohlcv: ohlcv_py.into_iter().map(|df| df.into()).collect(),
            extra_data: extra_data_py
                .into_iter()
                .map(|(k, v)| (k, v.into_iter().map(|df| df.into()).collect()))
                .collect(),
        })
    }
}
