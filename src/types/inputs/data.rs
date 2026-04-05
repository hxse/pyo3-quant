use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

pub type DataSource = HashMap<String, DataFrame>;

/// source 级别的真实预热 / 生效 / pack 边界。
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SourceRange {
    pub warmup_bars: usize,
    pub active_bars: usize,
    pub pack_bars: usize,
}

#[gen_stub_pymethods]
#[pymethods]
impl SourceRange {
    #[new]
    pub fn new(warmup_bars: usize, active_bars: usize, pack_bars: usize) -> Self {
        Self {
            warmup_bars,
            active_bars,
            pack_bars,
        }
    }
}

impl SourceRange {
    /// 中文注释：统一校验 source range 的基础代数约束。
    pub fn validate(&self, source_key: &str) -> PyResult<()> {
        if self.warmup_bars > self.pack_bars {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "ranges['{source_key}'].warmup_bars={} 不能大于 pack_bars={}",
                self.warmup_bars, self.pack_bars
            )));
        }
        if self.active_bars > self.pack_bars {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "ranges['{source_key}'].active_bars={} 不能大于 pack_bars={}",
                self.active_bars, self.pack_bars
            )));
        }
        if self.warmup_bars + self.active_bars != self.pack_bars {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "ranges['{source_key}'] 必须满足 warmup_bars + active_bars == pack_bars，当前为 {} + {} != {}",
                self.warmup_bars, self.active_bars, self.pack_bars
            )));
        }
        Ok(())
    }
}

/// 输入侧多周期数据包。
#[gen_stub_pyclass]
#[pyclass]
#[derive(Clone, Debug)]
pub struct DataPack {
    pub(crate) source: DataSource,
    pub(crate) mapping: DataFrame,
    pub(crate) skip_mask: Option<DataFrame>,
    pub(crate) ranges: HashMap<String, SourceRange>,
    pub(crate) base_data_key: String,
}

#[gen_stub_pymethods]
#[pymethods]
impl DataPack {
    #[new]
    #[pyo3(signature = (mapping, skip_mask, source, base_data_key, ranges))]
    pub fn new(
        py: Python<'_>,
        mapping: Bound<'_, PyAny>,
        skip_mask: Option<Bound<'_, PyAny>>,
        source: HashMap<String, Bound<'_, PyAny>>,
        base_data_key: String,
        ranges: HashMap<String, Py<SourceRange>>,
    ) -> PyResult<Self> {
        let mapping: PyDataFrame = mapping.extract()?;
        let skip_mask: Option<PyDataFrame> = match skip_mask {
            Some(value) => Some(value.extract()?),
            None => None,
        };
        let mut source_inner = HashMap::new();
        for (key, value) in source {
            let df: PyDataFrame = value.extract()?;
            source_inner.insert(key, df.into());
        }
        let mut ranges_inner = HashMap::new();
        for (key, value) in ranges {
            ranges_inner.insert(key, value.bind(py).borrow().clone());
        }
        Ok(Self {
            source: source_inner,
            mapping: mapping.into(),
            skip_mask: skip_mask.map(Into::into),
            ranges: ranges_inner,
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
            py_map.insert(k.clone(), py_df.into_pyobject(py)?.into_any().unbind());
        }
        Ok(py_map)
    }

    #[getter]
    pub fn ranges(&self, py: Python<'_>) -> PyResult<HashMap<String, Py<SourceRange>>> {
        let mut py_map = HashMap::new();
        for (k, v) in &self.ranges {
            py_map.insert(k.clone(), Py::new(py, v.clone())?);
        }
        Ok(py_map)
    }

    #[getter]
    pub fn base_data_key(&self) -> String {
        self.base_data_key.clone()
    }

    #[setter]
    pub fn set_mapping(&mut self, value: Bound<'_, PyAny>) -> PyResult<()> {
        let df: PyDataFrame = value.extract()?;
        self.mapping = df.into();
        Ok(())
    }

    #[setter]
    pub fn set_skip_mask(&mut self, value: Option<Bound<'_, PyAny>>) -> PyResult<()> {
        self.skip_mask = match value {
            Some(v) => {
                let df: PyDataFrame = v.extract()?;
                Some(df.into())
            }
            None => None,
        };
        Ok(())
    }

    #[setter]
    pub fn set_source(&mut self, value: HashMap<String, Bound<'_, PyAny>>) -> PyResult<()> {
        let mut source_inner = HashMap::new();
        for (key, item) in value {
            let df: PyDataFrame = item.extract()?;
            source_inner.insert(key, df.into());
        }
        self.source = source_inner;
        Ok(())
    }

    #[setter]
    pub fn set_base_data_key(&mut self, value: String) {
        self.base_data_key = value;
    }
}

impl DataPack {
    /// 中文注释：A1 先落只读 checked 构造，后续统一由 builder 负责完整校验。
    pub fn new_checked(
        source: DataSource,
        mapping: DataFrame,
        skip_mask: Option<DataFrame>,
        base_data_key: String,
        ranges: HashMap<String, SourceRange>,
    ) -> Self {
        Self {
            source,
            mapping,
            skip_mask,
            ranges,
            base_data_key,
        }
    }
}
