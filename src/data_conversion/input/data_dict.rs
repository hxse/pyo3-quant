use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

#[derive(Clone, FromPyObject)]
pub struct ProcessedDataDict {
    pub mapping: PyDataFrame,
    pub skip_mask: PyDataFrame,
    pub ohlcv: Vec<PyDataFrame>,
    pub extra_data: HashMap<String, Vec<PyDataFrame>>,
}

impl ProcessedDataDict {
    pub fn to_polars(
        self,
    ) -> (
        DataFrame,
        DataFrame,
        Vec<DataFrame>,
        HashMap<String, Vec<DataFrame>>,
    ) {
        let mapping = self.mapping.into();
        let skip_mask = self.skip_mask.into();
        let ohlcv: Vec<DataFrame> = self.ohlcv.into_iter().map(|df| df.into()).collect();
        let extra_data: HashMap<String, Vec<DataFrame>> = self
            .extra_data
            .into_iter()
            .map(|(k, v)| (k, v.into_iter().map(|df| df.into()).collect()))
            .collect();
        (mapping, skip_mask, ohlcv, extra_data)
    }
}
