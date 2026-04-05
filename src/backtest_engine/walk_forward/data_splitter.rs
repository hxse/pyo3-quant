use crate::types::{DataPack, SourceRange, WalkForwardConfig, WfWarmupMode};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;

#[derive(Debug, Clone)]
struct WindowGeometry {
    pub window_idx: usize,
    pub train_pack_range: (usize, usize),
    pub train_active_range: (usize, usize),
    pub test_pack_range: (usize, usize),
    pub test_active_range: (usize, usize),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceSliceRange {
    pub start: usize,
    pub end: usize,
}

#[derive(Debug, Clone)]
pub struct WindowSliceIndices {
    pub source_ranges: HashMap<String, SourceSliceRange>,
    pub ranges_draft: HashMap<String, SourceRange>,
}

#[derive(Debug, Clone)]
pub struct WindowIndices {
    pub train_pack: WindowSliceIndices,
    pub test_pack: WindowSliceIndices,
    pub test_active_base_row_range: (usize, usize),
}

#[derive(Debug, Clone)]
pub struct WindowPlan {
    pub window_idx: usize,
    pub indices: WindowIndices,
}

#[derive(Debug, Clone)]
pub struct WalkForwardPlan {
    pub required_warmup_by_key: HashMap<String, usize>,
    pub windows: Vec<WindowPlan>,
}

fn collect_projected_source_range(
    data: &DataPack,
    source_key: &str,
    pack_range: (usize, usize),
    active_range: (usize, usize),
    required_warmup: usize,
) -> PyResult<(SourceSliceRange, SourceRange)> {
    let pack_bars = pack_range.1.saturating_sub(pack_range.0);
    let active_bars = active_range.1.saturating_sub(active_range.0);
    if pack_bars == 0 || active_bars == 0 {
        return Err(PyValueError::new_err(format!(
            "source '{source_key}' 的窗口切片长度非法: pack_bars={pack_bars}, active_bars={active_bars}"
        )));
    }

    if source_key == data.base_data_key {
        let warmup_bars = active_range.0.saturating_sub(pack_range.0);
        return Ok((
            SourceSliceRange {
                start: pack_range.0,
                end: pack_range.1,
            },
            SourceRange::new(warmup_bars, active_bars, pack_bars),
        ));
    }

    let mapping_col = data
        .mapping
        .column(source_key)
        .map_err(|_| PyValueError::new_err(format!("mapping 中缺少 source 列 '{source_key}'")))?;
    let mapping_u32 = mapping_col
        .u32()
        .map_err(|_| PyValueError::new_err(format!("mapping['{source_key}'] 必须是 UInt32")))?;

    let pack_slice = mapping_u32.slice(pack_range.0 as i64, pack_bars);
    let mut min_idx: Option<usize> = None;
    let mut max_idx: Option<usize> = None;
    for idx in pack_slice.into_iter().flatten() {
        let i = idx as usize;
        min_idx = Some(min_idx.map_or(i, |v| v.min(i)));
        max_idx = Some(max_idx.map_or(i, |v| v.max(i)));
    }

    let first_active_mapped_idx = mapping_u32.get(active_range.0).ok_or_else(|| {
        PyValueError::new_err(format!(
            "source '{source_key}' 在 first active row={} 缺少映射",
            active_range.0
        ))
    })? as usize;

    let min_pack_idx = min_idx.ok_or_else(|| {
        PyValueError::new_err(format!(
            "source '{source_key}' 在 pack_range={:?} 内没有任何有效映射",
            pack_range
        ))
    })?;
    let max_pack_idx = max_idx.ok_or_else(|| {
        PyValueError::new_err(format!(
            "source '{source_key}' 在 pack_range={:?} 内没有任何有效映射",
            pack_range
        ))
    })?;

    if first_active_mapped_idx < required_warmup {
        return Err(PyValueError::new_err(format!(
            "source '{source_key}' 的左侧 warmup 不足: first_active_mapped_idx={} < required_warmup={}",
            first_active_mapped_idx, required_warmup
        )));
    }

    let source_start = min_pack_idx.min(first_active_mapped_idx - required_warmup);
    let source_end = max_pack_idx + 1;
    let source_pack_bars = source_end.saturating_sub(source_start);
    let warmup_bars = first_active_mapped_idx.saturating_sub(source_start);
    let retained_active_bars = source_pack_bars.saturating_sub(warmup_bars);

    Ok((
        SourceSliceRange {
            start: source_start,
            end: source_end,
        },
        SourceRange::new(warmup_bars, retained_active_bars, source_pack_bars),
    ))
}

pub fn build_window_slice_indices(
    data: &DataPack,
    pack_range: (usize, usize),
    active_range: (usize, usize),
    required_warmup_by_key: &HashMap<String, usize>,
) -> PyResult<WindowSliceIndices> {
    if pack_range.0 >= pack_range.1 {
        return Err(PyValueError::new_err(format!(
            "pack_range 非法: {:?}",
            pack_range
        )));
    }
    if active_range.0 >= active_range.1 {
        return Err(PyValueError::new_err(format!(
            "active_range 非法: {:?}",
            active_range
        )));
    }
    if active_range.0 < pack_range.0 || active_range.1 > pack_range.1 {
        return Err(PyValueError::new_err(format!(
            "active_range={:?} 必须完全位于 pack_range={:?} 内",
            active_range, pack_range
        )));
    }

    let mut source_keys = data.source.keys().cloned().collect::<Vec<_>>();
    source_keys.sort_unstable();
    let mut source_ranges = HashMap::with_capacity(source_keys.len());
    let mut ranges_draft = HashMap::with_capacity(source_keys.len());

    for source_key in source_keys {
        let required_warmup = required_warmup_by_key
            .get(&source_key)
            .copied()
            .unwrap_or(0);
        let (projected_range, projected_draft) = collect_projected_source_range(
            data,
            &source_key,
            pack_range,
            active_range,
            required_warmup,
        )?;
        source_ranges.insert(source_key.clone(), projected_range);
        ranges_draft.insert(source_key, projected_draft);
    }

    Ok(WindowSliceIndices {
        source_ranges,
        ranges_draft,
    })
}

/// 生成滚动窗口（统一按 active bars + min warmup 正式口径规划）。
///
/// 参数：
/// - `total_bars`：base 总 K 线数量。
/// - `config`：WF 配置。
/// - `indicator_warmup_bars_base`：base source 的指标预热需求（来自预检）。
fn generate_windows(
    total_bars: usize,
    config: &WalkForwardConfig,
    base_required_warmup: usize,
) -> PyResult<Vec<WindowGeometry>> {
    let mut windows = Vec::new();

    let train_active_bars = config.train_active_bars;
    let test_active_bars = config.test_active_bars;
    let train_warmup_bars = base_required_warmup.max(config.min_warmup_bars);
    let test_warmup_bars = base_required_warmup.max(config.min_warmup_bars).max(1);

    if train_active_bars == 0 {
        return Err(PyValueError::new_err("train_active_bars 必须 >= 1"));
    }
    if test_active_bars < 3 {
        return Err(PyValueError::new_err(format!(
            "test_active_bars 必须 >= 3（carry/开盘执行/尾部强平语义要求），当前={}",
            test_active_bars
        )));
    }

    // 中文注释：BorrowFromTrain 会把测试预热段借自训练 active 尾部，必须保证测试预热不长于训练 active。
    if matches!(config.warmup_mode, WfWarmupMode::BorrowFromTrain)
        && test_warmup_bars > train_active_bars
    {
        return Err(PyValueError::new_err(format!(
            "BorrowFromTrain 非法: test_warmup_bars={} > train_active_bars={}",
            test_warmup_bars, train_active_bars
        )));
    }

    // 中文注释：滚动步长固定等于测试 active 长度，保持相邻窗口 test_active 首尾相接。
    let step_len = test_active_bars;
    let mut shift = 0_usize;
    let mut window_id = 0_usize;

    loop {
        let train_pack_start = shift;
        let train_active_start = train_pack_start + train_warmup_bars;
        let train_active_end = train_active_start + train_active_bars;

        if train_active_end > total_bars {
            if windows.is_empty() {
                return Err(PyValueError::new_err(format!(
                    "第 0 窗训练 active 越界: train_active_end={} > total_bars={}",
                    train_active_end, total_bars
                )));
            }
            break;
        }

        let (test_pack_start, test_active_start) = match config.warmup_mode {
            WfWarmupMode::BorrowFromTrain => {
                (train_active_end - test_warmup_bars, train_active_end)
            }
            WfWarmupMode::ExtendTest => (train_active_end, train_active_end + test_warmup_bars),
        };

        if test_active_start >= total_bars {
            if windows.is_empty() {
                return Err(PyValueError::new_err(format!(
                    "第 0 窗测试 active 起点越界: test_active_start={} >= total_bars={}",
                    test_active_start, total_bars
                )));
            }
            break;
        }

        let test_active_end = (test_active_start + test_active_bars).min(total_bars);
        let retained_test_active_bars = test_active_end - test_active_start;
        if retained_test_active_bars < 3 {
            if windows.is_empty() {
                return Err(PyValueError::new_err(format!(
                    "第 0 窗测试 active 截短后不足 3 根: retained={}",
                    retained_test_active_bars
                )));
            }
            break;
        }

        windows.push(WindowGeometry {
            window_idx: window_id,
            train_pack_range: (train_pack_start, train_active_end),
            train_active_range: (train_active_start, train_active_end),
            test_pack_range: (test_pack_start, test_active_end),
            test_active_range: (test_active_start, test_active_end),
        });

        shift += step_len;
        window_id += 1;
    }

    if windows.is_empty() {
        return Err(PyValueError::new_err(
            "未生成任何窗口：请检查 train_active/test_active/min_warmup 与总样本长度",
        ));
    }

    Ok(windows)
}

/// 中文注释：D1 阶段统一把窗口几何入口收敛到这一层，runner 不再直接依赖其他窗口公式。
pub fn build_window_indices(
    data: &DataPack,
    config: &WalkForwardConfig,
    required_warmup_by_key: &HashMap<String, usize>,
) -> PyResult<WalkForwardPlan> {
    let base_df = data
        .source
        .get(&data.base_data_key)
        .ok_or_else(|| PyValueError::new_err("base_data_key 不存在于 source"))?;
    let total_bars = base_df.height();
    let base_required_warmup = required_warmup_by_key
        .get(&data.base_data_key)
        .copied()
        .ok_or_else(|| {
            PyValueError::new_err(format!(
                "required_warmup_by_key 缺少 base_data_key='{}'",
                data.base_data_key
            ))
        })?;
    let geometries = generate_windows(total_bars, config, base_required_warmup)?;
    let mut windows = Vec::with_capacity(geometries.len());
    for geometry in geometries {
        let train_pack = build_window_slice_indices(
            data,
            geometry.train_pack_range,
            geometry.train_active_range,
            required_warmup_by_key,
        )?;
        let test_pack = build_window_slice_indices(
            data,
            geometry.test_pack_range,
            geometry.test_active_range,
            required_warmup_by_key,
        )?;
        windows.push(WindowPlan {
            window_idx: geometry.window_idx,
            indices: WindowIndices {
                train_pack,
                test_pack,
                test_active_base_row_range: geometry.test_active_range,
            },
        });
    }
    Ok(WalkForwardPlan {
        required_warmup_by_key: required_warmup_by_key.clone(),
        windows,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backtest_engine::data_ops::build_full_data_pack;
    use polars::prelude::*;
    use pyo3::Python;
    use std::collections::HashMap;

    fn build_source_df(times: Vec<i64>) -> DataFrame {
        DataFrame::new(vec![
            Series::new("time".into(), times.clone()).into(),
            Series::new("open".into(), vec![1.0; times.len()]).into(),
            Series::new("high".into(), vec![1.0; times.len()]).into(),
            Series::new("low".into(), vec![1.0; times.len()]).into(),
            Series::new("close".into(), vec![1.0; times.len()]).into(),
            Series::new("volume".into(), vec![1.0; times.len()]).into(),
        ])
        .expect("df 应成功")
    }

    #[test]
    fn test_build_window_indices_contract() {
        let minute = 60_000_i64;
        let data = build_full_data_pack(
            HashMap::from([(
                "ohlcv_1m".to_string(),
                build_source_df((0..20).map(|i| i * minute).collect()),
            )]),
            "ohlcv_1m".to_string(),
            None,
            false,
        )
        .expect("data pack 应成功");
        let config = WalkForwardConfig {
            train_active_bars: 5,
            test_active_bars: 3,
            min_warmup_bars: 2,
            warmup_mode: WfWarmupMode::ExtendTest,
            ignore_indicator_warmup: false,
            optimizer_config: Default::default(),
        };

        let plan = build_window_indices(
            &data,
            &config,
            &HashMap::from([("ohlcv_1m".to_string(), 1_usize)]),
        )
        .expect("窗口规划应成功");
        assert_eq!(plan.required_warmup_by_key["ohlcv_1m"], 1);
        assert_eq!(plan.windows.len(), 3);
        assert_eq!(
            plan.windows[0].indices.train_pack.source_ranges["ohlcv_1m"],
            SourceSliceRange { start: 0, end: 7 }
        );
        assert_eq!(
            plan.windows[0].indices.train_pack.ranges_draft["ohlcv_1m"],
            SourceRange::new(2, 5, 7)
        );
        assert_eq!(
            plan.windows[0].indices.test_pack.source_ranges["ohlcv_1m"],
            SourceSliceRange { start: 7, end: 12 }
        );
        assert_eq!(
            plan.windows[0].indices.test_pack.ranges_draft["ohlcv_1m"],
            SourceRange::new(2, 3, 5)
        );
        assert_eq!(plan.windows[1].indices.test_active_base_row_range, (12, 15));
    }

    #[test]
    fn test_build_window_indices_borrow_from_train_contract() {
        let minute = 60_000_i64;
        let data = build_full_data_pack(
            HashMap::from([(
                "ohlcv_1m".to_string(),
                build_source_df((0..16).map(|i| i * minute).collect()),
            )]),
            "ohlcv_1m".to_string(),
            None,
            false,
        )
        .expect("data pack 应成功");
        let config = WalkForwardConfig {
            train_active_bars: 5,
            test_active_bars: 4,
            min_warmup_bars: 2,
            warmup_mode: WfWarmupMode::BorrowFromTrain,
            ignore_indicator_warmup: false,
            optimizer_config: Default::default(),
        };

        let plan = build_window_indices(
            &data,
            &config,
            &HashMap::from([("ohlcv_1m".to_string(), 1_usize)]),
        )
        .expect("窗口规划应成功");
        assert_eq!(
            plan.windows[0].indices.train_pack.source_ranges["ohlcv_1m"],
            SourceSliceRange { start: 0, end: 7 }
        );
        assert_eq!(
            plan.windows[0].indices.test_pack.source_ranges["ohlcv_1m"],
            SourceSliceRange { start: 5, end: 11 }
        );
        assert_eq!(plan.windows[0].indices.test_active_base_row_range, (7, 11));
        assert_eq!(
            plan.windows[1].indices.test_pack.source_ranges["ohlcv_1m"],
            SourceSliceRange { start: 9, end: 15 }
        );
    }

    #[test]
    fn test_build_window_slice_indices_preserves_coverage_left_expansion_in_ranges() {
        let minute = 60_000_i64;
        let data = build_full_data_pack(
            HashMap::from([
                (
                    "ohlcv_1m".to_string(),
                    build_source_df((0..8).map(|i| i * minute).collect()),
                ),
                (
                    "ohlcv_3m".to_string(),
                    build_source_df(vec![-3 * minute, 0, 3 * minute, 6 * minute]),
                ),
            ]),
            "ohlcv_1m".to_string(),
            None,
            false,
        )
        .expect("data pack 应成功");

        let indices = build_window_slice_indices(
            &data,
            (0, 5),
            (3, 5),
            &HashMap::from([
                ("ohlcv_1m".to_string(), 0_usize),
                ("ohlcv_3m".to_string(), 0_usize),
            ]),
        )
        .expect("slice indices 应成功");

        assert_eq!(
            indices.source_ranges["ohlcv_3m"],
            SourceSliceRange { start: 1, end: 3 }
        );
        assert_eq!(indices.ranges_draft["ohlcv_3m"], SourceRange::new(1, 1, 2));
    }

    #[test]
    fn test_build_window_slice_indices_rejects_projected_source_without_enough_left_warmup() {
        Python::initialize();

        let minute = 60_000_i64;
        let data = build_full_data_pack(
            HashMap::from([
                (
                    "ohlcv_1m".to_string(),
                    build_source_df((0..4).map(|i| i * minute).collect()),
                ),
                ("ohlcv_3m".to_string(), build_source_df(vec![0, 3 * minute])),
            ]),
            "ohlcv_1m".to_string(),
            None,
            false,
        )
        .expect("data pack 应成功");

        let err = build_window_slice_indices(
            &data,
            (0, 2),
            (0, 2),
            &HashMap::from([
                ("ohlcv_1m".to_string(), 0_usize),
                ("ohlcv_3m".to_string(), 1_usize),
            ]),
        )
        .expect_err("左侧 warmup 不足应失败");

        assert!(
            err.to_string().contains("左侧 warmup 不足"),
            "错误信息必须明确指出左侧 warmup 不足，实际={err}"
        );
    }
}
