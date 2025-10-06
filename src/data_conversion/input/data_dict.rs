use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::Bound;
use pyo3::exceptions::PyKeyError;
use polars::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

#[derive(Clone)]
pub struct ProcessedDataDict {
    pub mapping: DataFrame,
    pub skip_mask: DataFrame,
    pub data: HashMap<String, Vec<DataFrame>>,
}

// 实现 FromPyObject trait
impl<'py> FromPyObject<'py> for ProcessedDataDict {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        // 确保是字典类型
        let data_dict = ob.downcast::<PyDict>()?;

        // 1. 提取 mapping
        let mapping: DataFrame = data_dict
            .get_item("mapping")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'mapping' key"))?
            .extract::<PyDataFrame>()?
            .into();

        // 2. 提取 skip_mask
        let skip_mask: DataFrame = data_dict
            .get_item("skip_mask")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'skip_mask' key"))?
            .extract::<PyDataFrame>()?
            .into();

        // 3. 提取嵌套的 data 字典
        let data_item = data_dict
            .get_item("data")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'data' key"))?;
        let data_py_dict = data_item.downcast::<PyDict>()?;

        // 4. 手动转换 HashMap<String, Vec<DataFrame>>
        let mut data = HashMap::new();
        for item in data_py_dict.items() {
            let (key, value): (String, Bound<'_, pyo3::types::PyList>) = item.extract()?;

            let vec_py = value.extract::<Vec<PyDataFrame>>()?;
            let vec_df: Vec<DataFrame> = vec_py
                .into_iter()
                .map(|pydf| pydf.into())
                .collect();
            data.insert(key, vec_df);
        }

        Ok(ProcessedDataDict { mapping, skip_mask, data })
    }
}

// 简化后的 parse 函数
pub fn parse(data_dict: Bound<'_, PyDict>) -> PyResult<ProcessedDataDict> {
    data_dict.extract()
}
