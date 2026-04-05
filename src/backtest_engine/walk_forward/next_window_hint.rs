use crate::error::{OptimizerError, QuantError};
use crate::types::{NextWindowHint, WalkForwardConfig, WindowArtifact};

const MS_PER_DAY: f64 = 86_400_000.0;

/// 中文注释：提示算法只读取正式公开 WindowArtifact + config。
pub fn build_next_window_hint(
    window_results: &[WindowArtifact],
    config: &WalkForwardConfig,
) -> Result<NextWindowHint, QuantError> {
    let last_window = window_results
        .last()
        .ok_or_else(|| OptimizerError::InvalidConfig("no windows".into()))?;
    let observed_test_active_bars = active_bars(last_window)?;
    let last_test_active_start_ms = last_window.meta.test_active_time_range.0;
    let last_test_active_end_ms = last_window.meta.test_active_time_range.1;

    let expected_window_switch_time_ms = if observed_test_active_bars == config.test_active_bars {
        last_test_active_end_ms
    } else {
        let history_windows = &window_results[..window_results.len() - 1];
        let expected_test_active_span_ms = if history_windows.is_empty() {
            if observed_test_active_bars < 3 {
                return Err(OptimizerError::InvalidConfig(
                    "single-window NextWindowHint fallback requires observed test_active bars >= 3"
                        .into(),
                )
                .into());
            }
            let observed_span_ms =
                (last_test_active_end_ms - last_test_active_start_ms).max(0) as f64;
            observed_span_ms * (config.test_active_bars as f64 / observed_test_active_bars as f64)
        } else {
            median(
                &history_windows
                    .iter()
                    .map(|window| {
                        (window.meta.test_active_time_range.1
                            - window.meta.test_active_time_range.0)
                            .max(0) as f64
                    })
                    .collect::<Vec<_>>(),
            )?
        };

        last_test_active_start_ms + expected_test_active_span_ms.round() as i64
    };
    let remaining_span_ms = expected_window_switch_time_ms - last_test_active_end_ms;
    let eta_days = (remaining_span_ms as f64 / MS_PER_DAY).max(0.0);

    Ok(NextWindowHint {
        expected_window_switch_time_ms,
        eta_days,
        based_on_window_id: last_window.meta.window_id,
    })
}

fn active_bars(window: &WindowArtifact) -> Result<usize, QuantError> {
    window
        .test_pack_result
        .ranges
        .get(&window.test_pack_result.base_data_key)
        .map(|range| range.active_bars)
        .ok_or_else(|| {
            OptimizerError::InvalidConfig("window test_pack_result 缺少 base range".into()).into()
        })
}

fn median(values: &[f64]) -> Result<f64, QuantError> {
    if values.is_empty() {
        return Err(OptimizerError::InvalidConfig("median 输入不能为空".into()).into());
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).expect("无 NaN"));
    let mid = sorted.len() / 2;
    Ok(if sorted.len() % 2 == 1 {
        sorted[mid]
    } else {
        (sorted[mid - 1] + sorted[mid]) / 2.0
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{DataPack, ResultPack, SourceRange, WindowMeta};
    use polars::prelude::{DataFrame, NamedFrom, Series};
    use std::collections::HashMap;

    fn dummy_window(
        window_id: usize,
        time_range: (i64, i64),
        active_row_range: (usize, usize),
        active_bars: usize,
    ) -> WindowArtifact {
        let source = HashMap::from([(
            "ohlcv_1m".to_string(),
            DataFrame::new(vec![Series::new(
                "time".into(),
                vec![time_range.0, time_range.1],
            )
            .into()])
            .expect("source 应成功"),
        )]);
        let mapping = DataFrame::new(vec![Series::new(
            "time".into(),
            vec![time_range.0, time_range.1],
        )
        .into()])
        .expect("mapping 应成功");
        let pack = DataPack::new_checked(
            source.clone(),
            mapping.clone(),
            None,
            "ohlcv_1m".to_string(),
            HashMap::from([("ohlcv_1m".to_string(), SourceRange::new(0, 2, 2))]),
        );
        let result = ResultPack::new_checked(
            None,
            None,
            None,
            None,
            mapping,
            HashMap::from([(
                "ohlcv_1m".to_string(),
                SourceRange::new(0, active_bars, active_bars),
            )]),
            "ohlcv_1m".to_string(),
        );
        WindowArtifact {
            train_pack_data: pack.clone(),
            test_pack_data: pack,
            test_pack_result: result,
            meta: WindowMeta {
                window_id,
                best_params: crate::types::SingleParamSet::default(),
                has_cross_boundary_position: false,
                test_active_base_row_range: active_row_range,
                train_warmup_time_range: None,
                train_active_time_range: (0, 0),
                train_pack_time_range: (0, 0),
                test_warmup_time_range: time_range,
                test_active_time_range: time_range,
                test_pack_time_range: time_range,
            },
        }
    }

    #[test]
    fn test_next_window_hint_contract() {
        let config = WalkForwardConfig::new(
            10,
            6,
            2,
            crate::types::WfWarmupMode::ExtendTest,
            false,
            None,
        );
        let fallback_windows = vec![dummy_window(2, (100, 130), (10, 13), 3)];
        let fallback_hint =
            build_next_window_hint(&fallback_windows, &config).expect("单窗 fallback 应成功");
        assert_eq!(fallback_hint.expected_window_switch_time_ms, 160);
        assert!((fallback_hint.eta_days - (30.0 / 86_400_000.0)).abs() < 1e-12);
        assert_eq!(fallback_hint.based_on_window_id, 2);

        let err_windows = vec![dummy_window(3, (100, 120), (10, 12), 2)];
        assert!(build_next_window_hint(&err_windows, &config).is_err());

        let complete_windows = vec![
            dummy_window(0, (10, 40), (0, 6), 6),
            dummy_window(1, (50, 80), (6, 12), 6),
        ];
        let complete_hint =
            build_next_window_hint(&complete_windows, &config).expect("完整最后一窗应成功");
        assert_eq!(complete_hint.expected_window_switch_time_ms, 80);
        assert_eq!(complete_hint.eta_days, 0.0);
        assert_eq!(complete_hint.based_on_window_id, 1);
    }
}
