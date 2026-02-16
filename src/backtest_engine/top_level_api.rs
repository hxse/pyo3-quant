use crate::backtest_engine::utils;
use crate::error::QuantError;
use crate::types::{
    BacktestSummary, DataContainer, ParamContainer, SettingContainer, SingleParamSet,
    TemplateContainer,
};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rayon::prelude::*;

/// 纯 Rust 回测引擎主函数
///
/// 根据任务数量自动选择最优的执行策略：
/// - 单任务：直接执行，充分利用 Polars 的并发能力
/// - 多任务：使用 Rayon 并行，每个任务强制 Polars 单线程运行
///
/// # 参数
///
/// * `processed_data` - 预处理后的市场数据容器
/// * `processed_params` - 预处理后的回测参数集合
/// * `processed_template` - 预处理后的信号模板
/// * `processed_settings` - 预处理后的引擎设置
///
/// # 返回值
///
/// 返回所有回测任务的摘要结果列表
///
/// # 性能考虑
///
/// 函数会记录并输出总执行时间，便于性能监控和优化
pub fn run_backtest_engine(
    processed_data: &DataContainer,
    processed_params: &Vec<SingleParamSet>,
    processed_template: &TemplateContainer,
    processed_settings: &SettingContainer,
) -> Result<Vec<BacktestSummary>, QuantError> {
    let total_tasks = processed_params.len();

    let results: Vec<BacktestSummary> = if total_tasks == 1 {
        processed_params
            .iter()
            .map(|single_param| {
                execute_single_backtest(
                    processed_data,
                    single_param,
                    processed_template,
                    processed_settings,
                )
            })
            .collect::<Result<Vec<_>, QuantError>>()?
    } else {
        processed_params
            .par_iter()
            .map(|single_param| {
                utils::process_param_in_single_thread(|| {
                    execute_single_backtest(
                        processed_data,
                        single_param,
                        processed_template,
                        processed_settings,
                    )
                })
            })
            .collect::<Result<Vec<_>, QuantError>>()?
    };

    Ok(results)
}

/// 执行单个回测任务的核心函数
///
/// 按照执行阶段依次处理：
/// 1. 计算技术指标
/// 2. 生成交易信号
/// 3. 执行回测模拟
/// 4. 分析绩效结果
///
/// 支持增量计算：如果某个阶段已有结果，则跳过该阶段
///
/// # 内存管理
///
/// 在 `return_only_final` 模式下，会在每个阶段完成后立即释放不再需要的数据，
/// 以最小化内存占用。
///
/// # 参数
///
/// * `processed_data` - 市场数据
/// * `single_param` - 单个回测参数集
/// * `processed_template` - 信号模板
/// * `processed_settings` - 引擎设置
pub(crate) fn execute_single_backtest(
    processed_data: &DataContainer,
    single_param: &SingleParamSet,
    processed_template: &TemplateContainer,
    processed_settings: &SettingContainer,
) -> Result<BacktestSummary, QuantError> {
    // 0. 全局数据校验：检查基础数据的时间戳是否规范
    if let Some(base_df) = processed_data.source.get(&processed_data.base_data_key) {
        if let Ok(time_col) = base_df.column("time") {
            if let Ok(time_ca) = time_col.i64() {
                if let Some(first_ts) = time_ca.get(0) {
                    utils::validate_timestamp_ms(
                        first_ts,
                        &format!("Base Data ({})", processed_data.base_data_key),
                    )?;
                }
            }
        }
    }

    // 1. 初始化执行上下文
    let mut ctx = utils::BacktestContext::new();
    let stage = processed_settings.execution_stage;
    let return_only_final = processed_settings.return_only_final;

    // 2. 顺序执行各个阶段（每个方法内部处理 ExecutionStage 判断和缓存逻辑）
    ctx.execute_indicator_if_needed(stage, processed_data, &single_param.indicators)?;

    ctx.execute_signals_if_needed(
        stage,
        return_only_final,
        processed_data,
        &single_param.signal,
        &processed_template.signal,
    )?;

    ctx.execute_backtest_if_needed(
        stage,
        return_only_final,
        processed_data,
        &single_param.backtest,
    )?;

    ctx.execute_performance_if_needed(
        stage,
        return_only_final,
        processed_data,
        &single_param.performance,
    )?;

    // 3. 转换为最终结果
    Ok(ctx.into_summary(return_only_final, stage))
}

/// PyO3 接口函数：运行回测引擎
///
/// 这是 Python 端调用的入口函数，负责：
/// 1. 接收 Python 传递的参数
/// 2. 调用纯 Rust 回测引擎
/// 3. 将 Rust 结果转换为 Python 对象
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine",
    python = r#"
import pyo3_quant

def run_backtest_engine(
    data_dict: pyo3_quant.DataContainer,
    param_set: list[pyo3_quant.SingleParamSet],
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
) -> list[pyo3_quant.BacktestSummary]:
    """运行回测引擎"""
"#
)]
#[pyfunction(name = "run_backtest_engine")]
pub fn py_run_backtest_engine(
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    engine_settings: SettingContainer,
) -> PyResult<Vec<BacktestSummary>> {
    let results = run_backtest_engine(&data_dict, &param_set, &template, &engine_settings)?;
    Ok(results)
}

/// PyO3 接口函数：运行单个回测
///
/// 这是 Python 端调用的入口函数，直接执行单次回测而无需包装成列表。
#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine",
    python = r#"
import pyo3_quant

def run_single_backtest(
    data_dict: pyo3_quant.DataContainer,
    param: pyo3_quant.SingleParamSet,
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
) -> pyo3_quant.BacktestSummary:
    """运行单个回测"""
"#
)]
#[pyfunction(name = "run_single_backtest")]
pub fn py_run_single_backtest(
    data_dict: DataContainer,
    param: SingleParamSet,
    template: TemplateContainer,
    engine_settings: SettingContainer,
) -> PyResult<BacktestSummary> {
    let result = execute_single_backtest(&data_dict, &param, &template, &engine_settings)?;
    Ok(result)
}
