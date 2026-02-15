use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

pub type DataSource = HashMap<String, DataFrame>;

#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone)]
pub struct DataContainer {
    pub(crate) mapping: DataFrame,
    pub(crate) skip_mask: Option<DataFrame>,
    pub skip_mapping: HashMap<String, bool>,
    pub(crate) source: DataSource,
    pub base_data_key: String,
}

#[gen_stub_pymethods]
#[pymethods]
impl DataContainer {
    #[new]
    pub fn new(
        mapping: Bound<'_, PyAny>,
        skip_mask: Option<Bound<'_, PyAny>>,
        skip_mapping: HashMap<String, bool>,
        source: HashMap<String, Bound<'_, PyAny>>,
        base_data_key: String,
    ) -> PyResult<Self> {
        let mapping: PyDataFrame = mapping.extract()?;
        let skip_mask: Option<PyDataFrame> = match skip_mask {
            Some(b) => Some(b.extract()?),
            None => None,
        };
        let mut source_inner = HashMap::new();
        for (k, v) in source {
            let df: PyDataFrame = v.extract()?;
            source_inner.insert(k, df.into());
        }

        Ok(Self {
            mapping: mapping.into(),
            skip_mask: skip_mask.map(|df| df.into()),
            skip_mapping,
            source: source_inner,
            base_data_key,
        })
    }

    #[getter]
    pub fn mapping(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let py_df = PyDataFrame(self.mapping.clone());
        Ok(py_df.into_pyobject(py)?.into_any().unbind())
    }

    #[getter]
    pub fn skip_mask(&self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        match &self.skip_mask {
            Some(df) => {
                let py_df = PyDataFrame(df.clone());
                Ok(Some(py_df.into_pyobject(py)?.into_any().unbind()))
            }
            None => Ok(None),
        }
    }

    #[getter]
    pub fn source(&self, py: Python<'_>) -> PyResult<HashMap<String, Py<PyAny>>> {
        let mut py_map = HashMap::new();
        for (k, v) in &self.source {
            let py_df = PyDataFrame(v.clone());
            let py_obj = py_df.into_pyobject(py)?.into_any().unbind();
            py_map.insert(k.clone(), py_obj);
        }
        Ok(py_map)
    }

    #[setter]
    pub fn set_mapping(&mut self, value: Bound<'_, PyAny>) -> PyResult<()> {
        let df: PyDataFrame = value.extract()?;
        self.mapping = df.into();
        Ok(())
    }

    #[setter]
    pub fn set_skip_mask(&mut self, value: Option<Bound<'_, PyAny>>) -> PyResult<()> {
        match value {
            Some(v) => {
                let df: PyDataFrame = v.extract()?;
                self.skip_mask = Some(df.into());
            }
            None => self.skip_mask = None,
        }
        Ok(())
    }

    #[setter]
    pub fn set_source(&mut self, value: HashMap<String, Bound<'_, PyAny>>) -> PyResult<()> {
        let mut source_inner = HashMap::new();
        for (k, v) in value {
            let df: PyDataFrame = v.extract()?;
            source_inner.insert(k, df.into());
        }
        self.source = source_inner;
        Ok(())
    }

    #[getter]
    pub fn base_data_key(&self) -> String {
        self.base_data_key.clone()
    }

    #[setter]
    pub fn set_base_data_key(&mut self, value: String) {
        self.base_data_key = value;
    }

    #[getter]
    pub fn skip_mapping(&self) -> HashMap<String, bool> {
        self.skip_mapping.clone()
    }

    #[setter]
    pub fn set_skip_mapping(&mut self, value: HashMap<String, bool>) {
        self.skip_mapping = value;
    }
}
