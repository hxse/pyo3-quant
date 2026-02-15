use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum ParamType {
    Float,
    Integer,
    Boolean,
}

impl PyStubType for ParamType {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined("ParamType", pyo3_stub_gen::ModuleRef::Default)
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<ParamType>(),
        pyclass_name: "ParamType",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "参数类型",
        variants: &[
            ("Float", "浮点数"),
            ("Integer", "整数"),
            ("Boolean", "布尔值"),
        ],
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
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

#[gen_stub_pymethods]
#[pymethods]
impl Param {
    #[new]
    #[pyo3(signature = (value, min=None, max=None, dtype=None, optimize=false, log_scale=false, step=0.01))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        value: f64,
        min: Option<f64>,
        max: Option<f64>,
        dtype: Option<ParamType>,
        optimize: bool,
        log_scale: bool,
        step: f64,
    ) -> Self {
        let min = min.unwrap_or(value);
        let max = max.unwrap_or(value);
        let dtype = dtype.unwrap_or(ParamType::Float);
        Self {
            value,
            min,
            max,
            dtype,
            optimize,
            log_scale,
            step,
        }
    }
}
