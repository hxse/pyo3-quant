use crate::types::{WalkForwardConfig, WfWarmupMode};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[derive(Debug, Clone)]
pub struct WindowSpec {
    pub id: usize,
    pub train_range: (usize, usize),
    pub transition_range: (usize, usize),
    pub test_range: (usize, usize),
}

/// 生成滚动窗口（统一支持三模式）。
///
/// 参数：
/// - `total_bars`：base 总 K 线数量。
/// - `config`：WF 配置。
/// - `indicator_warmup_bars_base`：base source 的指标预热需求（来自预检）。
pub fn generate_windows(
    total_bars: usize,
    config: &WalkForwardConfig,
    indicator_warmup_bars_base: usize,
) -> PyResult<Vec<WindowSpec>> {
    let mut windows = Vec::new();

    let train_len = config.train_bars;
    let test_len = config.test_bars;
    let transition_cfg = config.transition_bars;

    if train_len == 0 || transition_cfg == 0 || test_len == 0 {
        return Err(PyValueError::new_err(format!(
            "窗口参数非法: total={}, train={}, transition={}, test={}",
            total_bars, train_len, transition_cfg, test_len
        )));
    }
    if test_len < 2 {
        return Err(PyValueError::new_err(format!(
            "test_bars 必须 >= 2（用于测试段倒数第二根注入），当前={}",
            test_len
        )));
    }

    // 中文注释：过渡期有效长度 E 由 warmup_mode 与预检 warmup 共同决定。
    let effective_transition = match config.wf_warmup_mode {
        WfWarmupMode::BorrowFromTrain | WfWarmupMode::ExtendTest => {
            indicator_warmup_bars_base.max(transition_cfg).max(1)
        }
        WfWarmupMode::NoWarmup => transition_cfg.max(1),
    };

    if effective_transition == 0 {
        return Err(PyValueError::new_err("effective_transition_bars 必须 >= 1"));
    }

    // 中文注释：BorrowFromTrain 会把过渡段放在训练尾部重叠，必须保证 E <= T。
    if matches!(config.wf_warmup_mode, WfWarmupMode::BorrowFromTrain)
        && effective_transition > train_len
    {
        return Err(PyValueError::new_err(format!(
            "BorrowFromTrain 非法: effective_transition_bars={} > train_bars={}",
            effective_transition, train_len
        )));
    }

    // 中文注释：滚动步长固定等于测试段长度，保持窗口测试段时间连续。
    let step_len = test_len;
    let mut base_start = 0_usize;
    let mut window_id = 0_usize;

    loop {
        let (train_range, transition_range, test_range) = match config.wf_warmup_mode {
            WfWarmupMode::BorrowFromTrain => {
                let train_start = base_start;
                let train_end = train_start + train_len;
                let transition_start = train_end - effective_transition;
                let transition_end = train_end;
                let test_start = train_end;
                let test_end = test_start + test_len;
                (
                    (train_start, train_end),
                    (transition_start, transition_end),
                    (test_start, test_end),
                )
            }
            WfWarmupMode::ExtendTest | WfWarmupMode::NoWarmup => {
                let train_start = base_start;
                let train_end = train_start + train_len;
                let transition_start = train_end;
                let transition_end = transition_start + effective_transition;
                let test_start = transition_end;
                let test_end = test_start + test_len;
                (
                    (train_start, train_end),
                    (transition_start, transition_end),
                    (test_start, test_end),
                )
            }
        };

        if test_range.1 > total_bars {
            break;
        }

        windows.push(WindowSpec {
            id: window_id,
            train_range,
            transition_range,
            test_range,
        });

        base_start += step_len;
        window_id += 1;
    }

    if windows.is_empty() {
        return Err(PyValueError::new_err(
            "未生成任何窗口：请检查 train/transition/test 与总样本长度",
        ));
    }

    Ok(windows)
}
