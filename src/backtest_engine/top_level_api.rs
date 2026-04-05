use crate::backtest_engine::data_ops::{
    build_result_pack, validate_base_data_key_is_smallest_interval,
};
use crate::backtest_engine::utils;
use crate::error::QuantError;
use crate::types::{
    DataPack, IndicatorResults, ParamContainer, ResultPack, SettingContainer, SingleParamSet,
    TemplateContainer,
};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rayon::prelude::*;

fn normalize_indicator_results(indicators: Option<IndicatorResults>) -> Option<IndicatorResults> {
    indicators.map(|raw| {
        raw.into_iter()
            .filter(|(_, df)| !(df.width() == 0 && df.height() == 0))
            .collect()
    })
}

/// 纯 Rust 回测引擎主函数
///
/// 根据任务数量自动选择最优的执行策略：
/// - 单任务：直接执行，充分利用 Polars 的并发能力
/// - 多任务：使用 Rayon 并行，每个任务强制 Polars 单线程运行
///
/// # 参数
///
/// * `processed_data` - 预处理后的市场数据 DataPack
/// * `processed_params` - 预处理后的回测参数集合
/// * `processed_template` - 预处理后的信号模板
/// * `processed_settings` - 预处理后的引擎设置
///
/// # 返回值
///
/// 返回所有回测任务的 ResultPack 列表
///
/// # 性能考虑
///
/// 函数会记录并输出总执行时间，便于性能监控和优化
pub fn run_backtest_engine(
    processed_data: &DataPack,
    processed_params: &Vec<SingleParamSet>,
    processed_template: &TemplateContainer,
    processed_settings: &SettingContainer,
) -> Result<Vec<ResultPack>, QuantError> {
    // 中文注释：回测引擎入口再次校验 base 最小周期约束，防止调用方绕过 mapping 构建流程。
    validate_base_data_key_is_smallest_interval(processed_data)?;

    let total_tasks = processed_params.len();

    let results: Vec<ResultPack> = if total_tasks == 1 {
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
    processed_data: &DataPack,
    single_param: &SingleParamSet,
    processed_template: &TemplateContainer,
    processed_settings: &SettingContainer,
) -> Result<ResultPack, QuantError> {
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

    let stage = processed_settings.execution_stage;
    let return_only_final = processed_settings.return_only_final;
    let mut indicator_dfs = None;
    let mut signals_df = None;
    let mut backtest_df = None;
    let mut performance = None;

    // 2. 顺序执行各个阶段（阶段判断仍保留在顶层主流程）
    if stage >= crate::types::ExecutionStage::Indicator {
        indicator_dfs = Some(crate::backtest_engine::indicators::calculate_indicators(
            processed_data,
            &single_param.indicators,
        )?);
    }

    if stage >= crate::types::ExecutionStage::Signals {
        if let Some(ref indicators) = indicator_dfs {
            signals_df = Some(crate::backtest_engine::signal_generator::generate_signals(
                processed_data,
                indicators,
                &single_param.signal,
                &processed_template.signal,
            )?);
            utils::maybe_release_indicators(return_only_final, &mut indicator_dfs);
        }
    }

    if stage >= crate::types::ExecutionStage::Backtest {
        if let Some(ref signals) = signals_df {
            let raw_backtest = crate::backtest_engine::backtester::run_backtest(
                processed_data,
                signals,
                &single_param.backtest,
            )?;
            backtest_df = Some(raw_backtest);
            utils::maybe_release_signals(return_only_final, &mut signals_df);
        }
    }

    if stage >= crate::types::ExecutionStage::Performance {
        if let Some(ref backtest) = backtest_df {
            performance = Some(
                crate::backtest_engine::performance_analyzer::analyze_performance(
                    processed_data,
                    backtest,
                    &single_param.performance,
                )?,
            );
            utils::maybe_release_backtest(return_only_final, &mut backtest_df);
        }
    }

    build_result_pack(
        processed_data,
        normalize_indicator_results(indicator_dfs),
        signals_df,
        backtest_df,
        performance,
    )
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
    data: pyo3_quant.DataPack,
    params: list[pyo3_quant.SingleParamSet],
    template: pyo3_quant.TemplateContainer,
    engine_settings: pyo3_quant.SettingContainer,
) -> list[pyo3_quant.ResultPack]:
    """运行回测引擎"""
"#
)]
#[pyfunction(name = "run_backtest_engine")]
pub fn py_run_backtest_engine(
    data: DataPack,
    params: ParamContainer,
    template: TemplateContainer,
    engine_settings: SettingContainer,
) -> PyResult<Vec<ResultPack>> {
    let results = run_backtest_engine(&data, &params, &template, &engine_settings)?;
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
    // 中文注释：单次回测入口与批量入口保持同一数据约束。
    validate_base_data_key_is_smallest_interval(&data)?;
    let result = execute_single_backtest(&data, &param, &template, &engine_settings)?;
    Ok(result)
}
