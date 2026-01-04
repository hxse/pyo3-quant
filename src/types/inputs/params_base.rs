use pyo3::prelude::*;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParamType {
    Float,
    Integer,
    Boolean,
}

impl<'py> FromPyObject<'py> for ParamType {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "float" => Ok(ParamType::Float),
            "integer" => Ok(ParamType::Integer),
            "boolean" => Ok(ParamType::Boolean),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid ParamType: {}",
                s
            ))),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Param {
    /// 当前参数值
    pub value: f64,
    /// 参数最小值限制
    pub min: f64,
    /// 参数最大值限制
    pub max: f64,
    /// 参数类型
    pub dtype: ParamType,
    /// 是否开启参数优化，在参数优化过程中使用
    pub optimize: bool,
    /// 是否开启对数分布，用于参数优化时的采样策略
    pub log_scale: bool,
    /// 最小精度
    pub step: f64,
}

impl<'source> FromPyObject<'source> for Param {
    fn extract_bound(ob: &Bound<'source, PyAny>) -> PyResult<Self> {
        Ok(Self {
            value: ob.getattr("value")?.extract()?,
            min: ob.getattr("min")?.extract()?,
            max: ob.getattr("max")?.extract()?,
            dtype: ob.getattr("dtype")?.extract()?,
            optimize: ob.getattr("optimize")?.extract()?,
            log_scale: ob.getattr("log_scale")?.extract()?,
            step: ob.getattr("step")?.extract()?,
        })
    }
}
