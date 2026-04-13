use crate::backtest_engine::{
    build_public_result_pack, compile_public_setting_to_request, execute_single_pipeline, utils,
};
use crate::error::QuantError;
use crate::types::{DataPack, ParamContainer, ResultPack, SettingContainer, SingleParamSet, TemplateContainer};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rayon::prelude::*;

pub fn run_batch_backtest(
    data: &DataPack,
    params: &Vec<SingleParamSet>,
    template: &TemplateContainer,
    engine_settings: &SettingContainer,
) -> Result<Vec<ResultPack>, QuantError> {
    let request = compile_public_setting_to_request(engine_settings)?;
    let total_tasks = params.len();

    if total_tasks == 1 {
        params
            .iter()
            .map(|param| {
                let output = execute_single_pipeline(data, param, template, request.clone())?;
                build_public_result_pack(data, output)
            })
            .collect()
    } else {
        params
            .par_iter()
            .map(|param| {
                utils::process_param_in_single_thread(|| {
                    let output =
                        execute_single_pipeline(data, param, template, request.clone())?;
                    build_public_result_pack(data, output)
                })
            })
            .collect()
    }
}

pub fn run_single_backtest(
    data: &DataPack,
    param: &SingleParamSet,
    template: &TemplateContainer,
    engine_settings: &SettingContainer,
) -> Result<ResultPack, QuantError> {
    let request = compile_public_setting_to_request(engine_settings)?;
    let output = execute_single_pipeline(data, param, template, request)?;
    build_public_result_pack(data, output)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine",
    python = r#"
import pyo3_quant

def run_batch_backtest(
    data: pyo3_quant.DataPack,
    params: list[pyo3_quant.SingleParamSet],
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
) -> list[pyo3_quant.ResultPack]:
    """运行批量回测"""
"#
)]
#[pyfunction(name = "run_batch_backtest")]
pub fn py_run_batch_backtest(
    data: DataPack,
    params: ParamContainer,
    template: TemplateContainer,
    engine_settings: SettingContainer,
) -> PyResult<Vec<ResultPack>> {
    run_batch_backtest(&data, &params, &template, &engine_settings).map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine",
    python = r#"
import pyo3_quant

def run_single_backtest(
    data: pyo3_quant.DataPack,
    param: pyo3_quant.SingleParamSet,
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
) -> pyo3_quant.ResultPack:
    """运行单个回测"""
"#
)]
#[pyfunction(name = "run_single_backtest")]
pub fn py_run_single_backtest(
    data: DataPack,
    param: SingleParamSet,
    template: TemplateContainer,
    engine_settings: SettingContainer,
) -> PyResult<ResultPack> {
    run_single_backtest(&data, &param, &template, &engine_settings).map_err(Into::into)
}
