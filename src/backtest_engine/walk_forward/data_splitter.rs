use crate::types::WalkForwardConfig;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[derive(Debug, Clone)]
pub struct WindowSpec {
    pub id: usize,
    pub train_range: (usize, usize),
    pub transition_range: (usize, usize),
    pub test_range: (usize, usize),
}

/// 生成滚动窗口
///
/// # 参数
/// * `total_bars` - 总K线数量
/// * `config` - 配置
///
/// # 返回
/// 窗口列表或错误
pub fn generate_windows(
    total_bars: usize,
    config: &WalkForwardConfig,
) -> PyResult<Vec<WindowSpec>> {
    let mut windows = Vec::new();
    let train_len = (total_bars as f64 * config.train_ratio) as usize;
    let transition_len = (total_bars as f64 * config.transition_ratio) as usize;
    let test_len = (total_bars as f64 * config.test_ratio) as usize;
    // 破坏性更新：滚动步长强制等于测试期长度，移除独立 step_ratio。
    let step_len = test_len;

    if train_len == 0 || transition_len == 0 || test_len == 0 {
        return Err(PyValueError::new_err(format!(
            "Window size too small: total={}, train={}, transition={}, test={}",
            total_bars, train_len, transition_len, test_len
        )));
    }

    if train_len + transition_len + test_len > total_bars {
        return Err(PyValueError::new_err(
            "Initial window size (train + transition + test) exceeds total data size",
        ));
    }

    // 窗口生成逻辑
    // Start from idx 0
    // Window i:
    // Train: [start, start + train_len)
    // Test:  [start + train_len, start + train_len + test_len)
    // Next start: start + step_len

    let mut start_idx = 0;
    let mut window_id = 0;

    while start_idx + train_len + transition_len + test_len <= total_bars {
        let train_start = start_idx;
        let train_end = start_idx + train_len; // Exclusive
        let transition_start = train_end;
        let transition_end = transition_start + transition_len;
        let test_start = transition_end;
        let test_end = test_start + test_len; // Exclusive

        windows.push(WindowSpec {
            id: window_id,
            train_range: (train_start, train_end),
            transition_range: (transition_start, transition_end),
            test_range: (test_start, test_end),
        });

        start_idx += step_len;
        window_id += 1;
    }

    Ok(windows)
}
