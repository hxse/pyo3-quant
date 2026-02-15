use super::runner::{run_optimization, run_optimization_generic, EvalMode};
use crate::types::{
    BenchmarkFunction, DataContainer, OptimizationResult, OptimizerConfig, Param, ParamType,
    SettingContainer, SingleParamSet, TemplateContainer,
};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

/// Python 接口：运行基准函数优化
#[gen_stub_pyfunction(module = "pyo3_quant.backtest_engine.optimizer")]
#[pyfunction]
#[pyo3(signature = (config, function, bounds, seed=None))]
pub fn py_run_optimizer_benchmark(
    config: OptimizerConfig,
    function: BenchmarkFunction,
    bounds: Vec<(f64, f64)>,
    seed: Option<u64>, // TODO: 用于初始化 param 的随机性？目前 generic 内部自建 RNG
) -> PyResult<(Vec<f64>, f64)> {
    let _ = seed;
    // 构造一个假的 SingleParamSet，包含需要优化的参数
    // 我们利用 indicators 参数作为载体

    let mut indicators = HashMap::new();
    let mut group = HashMap::new();

    for (i, (min, max)) in bounds.iter().enumerate() {
        let name = format!("x{}", i);
        let p = Param {
            value: 0.0,
            min: *min,
            max: *max,
            dtype: ParamType::Float,
            optimize: true,
            log_scale: false,
            step: 0.0,
        };
        // 注意：基准函数通常是连续的，ParamType::Float 是合适的

        group.insert(name, p);
    }
    indicators.insert(
        "mock_tf".to_string(),
        HashMap::from([("g1".to_string(), group)]),
    );

    let param_set = SingleParamSet {
        indicators,
        signal: Default::default(),
        backtest: crate::backtest_engine::optimizer::test_helpers::create_dummy_backtest_params(),
        performance:
            crate::backtest_engine::optimizer::test_helpers::create_dummy_performance_params(),
    };

    let result = run_optimization_generic(
        EvalMode::BenchmarkFunction { function },
        &param_set,
        &config,
    )
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

    // 从 OptimizationResult 中提取 best_params 并转换回 Vec<f64>
    let best_params_set = result.best_params;
    let mut best_vals = Vec::with_capacity(bounds.len());

    // 从 mock_tf -> g1 组中提取
    if let Some(tf_map) = best_params_set.indicators.get("mock_tf") {
        if let Some(g_map) = tf_map.get("g1") {
            for i in 0..bounds.len() {
                let key = format!("x{}", i);
                if let Some(param) = g_map.get(&key) {
                    best_vals.push(param.value);
                } else {
                    best_vals.push(0.0);
                }
            }
        }
    }

    // 优化器求的是最大值（-val），所以返回时取负还原
    let best_val = result
        .top_k_samples
        .first()
        .map(|s| s.metric_value)
        .unwrap_or(0.0);
    Ok((best_vals, -best_val))
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.optimizer",
    python = r#"
def py_run_optimizer(
    data_dict: _pyo3_quant.DataContainer,
    param: _pyo3_quant.SingleParamSet,
    template: _pyo3_quant.TemplateContainer,
    engine_settings: _pyo3_quant.SettingContainer,
    optimizer_config: _pyo3_quant.OptimizerConfig,
) -> _pyo3_quant.OptimizationResult:
    """运行优化器"""
"#
)]
#[pyfunction]
pub fn py_run_optimizer(
    data_dict: DataContainer,
    param: SingleParamSet,
    template: TemplateContainer,
    engine_settings: SettingContainer,
    optimizer_config: OptimizerConfig,
) -> PyResult<OptimizationResult> {
    run_optimization(
        &data_dict,
        &param,
        &template,
        &engine_settings,
        &optimizer_config,
    )
    .map_err(|e| e.into())
}
