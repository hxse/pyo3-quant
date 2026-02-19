pub mod backtest_engine;
mod error;
pub mod types;

use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

#[pymodule(name = "_pyo3_quant")]
fn _pyo3_quant(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Register types
    m.add_class::<types::Param>()?;
    m.add_class::<types::ParamType>()?;
    m.add_class::<types::BacktestParams>()?;
    m.add_class::<types::PerformanceMetric>()?;
    m.add_class::<types::PerformanceParams>()?;
    m.add_class::<types::SingleParamSet>()?;
    m.add_class::<types::DataContainer>()?;
    m.add_class::<types::OptimizerConfig>()?;
    m.add_class::<types::OptimizeMetric>()?;
    m.add_class::<types::BenchmarkFunction>()?;
    m.add_class::<types::SettingContainer>()?;
    m.add_class::<types::ExecutionStage>()?;
    m.add_class::<types::LogicOp>()?;
    m.add_class::<types::SignalGroup>()?;
    m.add_class::<types::SignalTemplate>()?;
    m.add_class::<types::TemplateContainer>()?;
    m.add_class::<types::WalkForwardConfig>()?;
    m.add_class::<types::SensitivityConfig>()?;

    m.add_class::<types::BacktestSummary>()?;
    m.add_class::<types::RoundSummary>()?;
    m.add_class::<types::SamplePoint>()?;
    m.add_class::<types::OptimizationResult>()?;
    m.add_class::<types::NextWindowHint>()?;
    m.add_class::<types::WindowArtifact>()?;
    m.add_class::<types::StitchedArtifact>()?;
    m.add_class::<types::WalkForwardResult>()?;
    m.add_class::<types::SensitivitySample>()?;
    m.add_class::<types::SensitivityResult>()?;

    let backtest_engine_submodule = PyModule::new(m.py(), "backtest_engine")?;
    backtest_engine::register_py_module(&backtest_engine_submodule)?;
    m.add_submodule(&backtest_engine_submodule)?;

    let errors_submodule = PyModule::new(m.py(), "errors")?;
    error::py_interface::register_py_exceptions(&errors_submodule)?;
    m.add_submodule(&errors_submodule)?;

    // 将公开子模块注册到 sys.modules，确保可以通过 pyo3_quant.* 直接导入。
    // 这是 PyO3 推荐的注册方式，可避免 Python 侧手工动态注入成员。
    let sys_modules = m.py().import("sys")?.getattr("modules")?;
    sys_modules.set_item("pyo3_quant.backtest_engine", &backtest_engine_submodule)?;
    sys_modules.set_item("pyo3_quant.errors", &errors_submodule)?;

    Ok(())
}

// Note: To avoid PyStubType orphan rule for PyDataFrame, we use PyAny in pyfunctions.

define_stub_info_gatherer!(stub_info);
