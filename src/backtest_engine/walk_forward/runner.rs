use crate::backtest_engine::optimizer::runner::run_optimization;
use crate::backtest_engine::walk_forward::data_splitter::generate_windows;
use crate::error::QuantError;
use crate::types::OptimizerConfig;
use crate::types::WalkForwardConfig;
use crate::types::{DataContainer, ParamContainer, SettingContainer, TemplateContainer};
use crate::types::{WalkForwardResult, WindowResult};
use pyo3::prelude::*;

/// 运行向前滚动优化
pub fn run_walk_forward(
    data_dict: &DataContainer,
    param_set: &ParamContainer,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, QuantError> {
    // 1. 获取总数据长度
    // 获取第一个 DataFrame 的长度作为 total_bars
    let total_bars = if let Some(first_df) = data_dict.source.values().next() {
        first_df.height()
    } else {
        return Err(
            PyErr::new::<pyo3::exceptions::PyValueError, _>("No data in DataContainer").into(),
        );
    };

    // 2. 生成窗口
    let windows = generate_windows(total_bars, config)?;

    let mut window_results = Vec::new();
    let mut prev_top_k: Option<Vec<Vec<f64>>> = None;

    // 3. 遍历窗口
    for window in windows {
        // 3.1 准备切片数据
        let train_len = window.train_range.1 - window.train_range.0;
        let train_data = slice_data_container(data_dict, window.train_range.0, train_len);

        // 3.2 配置优化器
        let mut opt_config = config.optimizer_config.clone();

        // 继承权重
        if config.inherit_prior {
            if let Some(ref priors) = prev_top_k {
                if !priors.is_empty() {
                    opt_config.init_samples = Some(priors.clone());
                    // 可以适当调大 explore_ratio 以防止陷入局部
                }
            }
        }

        // 3.3 运行训练集优化
        // 使用 slice 后的 train_data
        let train_result =
            run_optimization(&train_data, param_set, template, settings, &opt_config)?;

        // 3.4 准备测试集回测
        let test_len = window.test_range.1 - window.test_range.0;
        let test_data = slice_data_container(data_dict, window.test_range.0, test_len);

        let test_calmar;
        let test_return;

        if let Some(best_values) = &train_result.best_sample_values {
            // 构造只运行一次的配置
            let mut test_opt_config = OptimizerConfig::default();
            test_opt_config.max_samples = 1;
            test_opt_config.min_samples = 0; // Disable min check
                                             // test_opt_config.min_rounds = 0; // 已删除
            test_opt_config.stop_patience = 0; // Disable stop
            test_opt_config.init_samples = Some(vec![best_values.clone()]);
            test_opt_config.samples_per_round = 1;

            let test_run_res =
                run_optimization(&test_data, param_set, template, settings, &test_opt_config)?;

            test_calmar = test_run_res.best_calmar;
            test_return = 0.0;
        } else {
            // 训练失败
            test_calmar = 0.0;
            test_return = 0.0;
        }

        // 3.5 记录结果
        window_results.push(WindowResult {
            window_id: window.id,
            train_range: window.train_range,
            test_range: window.test_range,
            best_params: train_result.best_params, // 记录训练得出的最佳参数
            train_calmar: train_result.best_calmar,
            test_calmar,
            train_return: 0.0, // 需要扩展 OptimizationResult 才能获取
            test_return,
        });

        // 3.6 更新 Prior (Top K)
        let current_top_k: Vec<Vec<f64>> = train_result
            .top_k_samples
            .iter()
            .map(|s| s.values.clone())
            .collect();

        prev_top_k = Some(current_top_k);

        println!(
            "Window {} Finished. Train Calmar: {:.4}, Test Calmar: {:.4}",
            window.id, train_result.best_calmar, test_calmar
        );
    }

    // 4. 汇总
    let avg_test_calmar = if window_results.is_empty() {
        0.0
    } else {
        window_results.iter().map(|w| w.test_calmar).sum::<f64>() / window_results.len() as f64
    };

    Ok(WalkForwardResult {
        windows: window_results,
        aggregate_test_calmar: avg_test_calmar,
        aggregate_test_return: 0.0,
    })
}

fn slice_data_container(data: &DataContainer, start: usize, len: usize) -> DataContainer {
    // Slice Source
    let sliced_source: std::collections::HashMap<_, _> = data
        .source
        .iter()
        .map(|(k, df)| (k.clone(), df.slice(start as i64, len)))
        .collect();

    // Slice Mapping
    // mapping 也是 DataFrame
    let sliced_mapping = data.mapping.slice(start as i64, len);

    // Slice Skip Mask
    let sliced_skip_mask = data
        .skip_mask
        .as_ref()
        .map(|df| df.slice(start as i64, len));

    DataContainer {
        source: sliced_source,
        mapping: sliced_mapping,
        skip_mask: sliced_skip_mask,
        skip_mapping: data.skip_mapping.clone(),
        base_data_key: data.base_data_key.clone(),
    }
}

/// Python 接口
#[pyfunction]
pub fn py_run_walk_forward(
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    engine_settings: SettingContainer,
    config: WalkForwardConfig,
) -> PyResult<WalkForwardResult> {
    run_walk_forward(&data_dict, &param_set, &template, &engine_settings, &config)
        .map_err(|e| e.into())
}
