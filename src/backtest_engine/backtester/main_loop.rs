// src/backtest_engine/backtester/main_loop.rs
use super::data_preparer::PreparedData;
use super::output::OutputBuffers;
use super::state::BacktestState;
use crate::data_conversion::BacktestParams;
use crate::error::backtest_error::BacktestError;

// 引入宏（由于宏使用 #[macro_export] 标注，需要从 crate 根级别导入）
use crate::{validate_output_buffers, validate_prepared_data};

/// 运行回测主循环
pub fn run_main_loop(
    prepared_data: &PreparedData,
    state: &mut BacktestState,
    mut buffers: OutputBuffers,
    backtest_params: &BacktestParams,
) -> Result<OutputBuffers, BacktestError> {
    // ---------- 1. 长度校验（宏展开） ----------
    let data_length = validate_prepared_data!(prepared_data, data_length);

    if data_length == 0 {
        return Ok(buffers);
    }

    // ---------- 2. OutputBuffers 长度校验 ----------
    // 这里的校验同样在 Release 模式下帮助编译器推断所有 buffers[i] 安全
    validate_output_buffers!(buffers, data_length);

    // ---------- 3. 主循环 ----------
    // 索引 0 已经在外部（或在 buffers 初始化时）填好默认值
    if data_length > 1 {
        for i in 1..data_length {
            // 所有切片访问都已在宏中证明长度相等 → 边界检查被消除
            let _time = prepared_data.time[i];
            let _open = prepared_data.open[i];
            let _high = prepared_data.high[i];
            let _low = prepared_data.low[i];
            let _close = prepared_data.close[i];
            let _volume = prepared_data.volume[i];

            let _enter_long = prepared_data.enter_long[i];
            let _exit_long = prepared_data.exit_long[i];
            let _enter_short = prepared_data.enter_short[i];
            let _exit_short = prepared_data.exit_short[i];
            let _atr = prepared_data.atr.as_ref().map(|atr_vec| atr_vec[i]);

            // 示例：直接索引写入（边界检查已消除）
            buffers.balance[i] = i as f64;
            // …… 您的完整回测逻辑写在这里 …
        }
    }

    Ok(buffers)
}
