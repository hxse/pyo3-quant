use super::state::{
    current_bar_data::CurrentBarData, BacktestState, OutputBuffersIter, PreparedDataIter,
    WriteConfig,
};
use super::{buffer_slices::extract_slices, data_preparer::PreparedData, output::OutputBuffers};
use crate::error::backtest_error::BacktestError;
use crate::types::BacktestParams;

/// 运行回测主循环
pub fn run_main_loop(
    mut prepared_data: PreparedData,
    backtest_params: &BacktestParams,
) -> Result<OutputBuffers, BacktestError> {
    let data_length = prepared_data.time.len();

    // 创建输出缓冲区
    let mut buffers = OutputBuffers::new(backtest_params, data_length);

    if data_length <= 2 {
        return Ok(buffers);
    }

    // 初始化回测状态
    let mut state = BacktestState::new(backtest_params, &prepared_data);

    // 初始化第0行和第1行数据 (仅写入初始状态)
    initialize_buffer_rows_0_and_1(&mut buffers, &mut state, &prepared_data);

    // 初始化滚动状态 (针对 i=2，前值是 i=1)
    let mut prev_bar = CurrentBarData::new(&prepared_data, 1);

    // 预先构建写入配置，确定哪些可选列需要写入
    let write_config = WriteConfig::from_params(backtest_params);

    // 主循环：从 i=2 开始迭代
    let input_iter = PreparedDataIter::new(&prepared_data, 2);
    let output_iter = OutputBuffersIter::new(&mut buffers, 2);

    for ((i, current_bar), mut output_row) in input_iter.zip(output_iter) {
        state.current_index = i;
        state.current_bar = current_bar;
        state.prev_bar = prev_bar;

        if state.should_skip_current_bar() {
            state.reset_position_on_skip();
            state.reset_capital_on_skip();
        } else {
            state.calculate_position(backtest_params);
            state.calculate_capital(backtest_params);
        }

        output_row.write_from_state_grouped(&state, &write_config);

        prev_bar = current_bar;
    }

    // ATR 数据赋值
    if prepared_data.atr.is_some() {
        buffers.atr = prepared_data.atr.take();
    }

    Ok(buffers)
}

/// 初始化输出缓冲区的第0行和第1行数据
#[inline(never)]
fn initialize_buffer_rows_0_and_1(
    buffers: &mut OutputBuffers,
    state: &mut BacktestState<'_>,
    prepared_data: &PreparedData<'_>,
) {
    let (mut fixed, mut opt) = extract_slices(buffers);

    // 第0行 (如果存在)
    if !prepared_data.time.is_empty() {
        state.current_index = 0;
        state.current_bar = CurrentBarData::new(prepared_data, 0);
        fixed.write(state, 0);
        opt.write(state, 0);
    }

    // 第1行 (如果存在)
    if prepared_data.time.len() > 1 {
        state.current_index = 1;
        state.prev_bar = state.current_bar; // bar[0]
        state.current_bar = CurrentBarData::new(prepared_data, 1);

        fixed.write(state, 1);
        opt.write(state, 1);
    }
}
