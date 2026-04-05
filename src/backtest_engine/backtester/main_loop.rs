use super::output_schema::ScheduleOutputSchema;
use super::params_selector::{select_params_for_row, ParamsSelector};
use super::state::{
    current_bar_data::CurrentBarData, BacktestState, OutputBuffersIter, PreparedDataIter,
    WriteConfig,
};
use super::{data_preparer::PreparedData, output::OutputBuffers};
use crate::error::backtest_error::BacktestError;
use crate::types::BacktestParams;

/// 运行回测主循环
pub fn legacy_run_main_loop(
    prepared_data: PreparedData,
    backtest_params: &BacktestParams,
) -> Result<OutputBuffers, BacktestError> {
    let data_length = prepared_data.time.len();

    // 创建输出缓冲区
    let mut buffers = OutputBuffers::new(backtest_params, data_length);

    // 初始化回测状态
    let mut state = BacktestState::new(backtest_params, &prepared_data);

    // 预先构建写入配置
    let config = WriteConfig::from_params(backtest_params);

    // 初始化第0行和第1行
    initialize_buffer_rows_0_and_1(&mut buffers, &mut state, &prepared_data, &config);

    if data_length <= 2 {
        return Ok(buffers);
    }

    // 从第2行开始主循环
    // 使用迭代器模式避免边界检查
    // 跳过前2行（已被初始化）
    let mut buf_iter = OutputBuffersIter::new(&mut buffers, 2);
    let mut data_iter = PreparedDataIter::new(&prepared_data, 2);

    // PreparedDataIter 产生 (usize, CurrentBarData)
    while let (Some(mut row), Some((index, current_bar))) = (buf_iter.next(), data_iter.next()) {
        state.current_index = index;
        state.prev_bar = state.current_bar;
        state.current_bar = current_bar;

        // 核心回测逻辑
        state.calculate_position(backtest_params);
        state.calculate_capital(backtest_params);

        // 写入当前行结果
        row.write(&state, &config);
    }

    Ok(buffers)
}

/// 中文注释：kernel 统一只从 selector 取当前参数，并保持既定初始化顺序。
pub fn run_backtest_kernel(
    prepared_data: PreparedData,
    mut params_selector: ParamsSelector<'_>,
    output_schema: ScheduleOutputSchema,
) -> Result<OutputBuffers, BacktestError> {
    let data_length = prepared_data.time.len();
    let init_params = select_params_for_row(&mut params_selector, 0)
        .map_err(|e| BacktestError::ValidationError(e.to_string()))?;

    let mut buffers = OutputBuffers::from_schema(&output_schema, data_length);
    let mut state = BacktestState::new(init_params, &prepared_data);
    let init_config = WriteConfig::from_params(init_params);

    initialize_buffer_rows_0_and_1(&mut buffers, &mut state, &prepared_data, &init_config);

    if data_length <= 2 {
        return Ok(buffers);
    }

    let mut buf_iter = OutputBuffersIter::new(&mut buffers, 2);
    let mut data_iter = PreparedDataIter::new(&prepared_data, 2);

    while let (Some(mut row), Some((index, current_bar))) = (buf_iter.next(), data_iter.next()) {
        let current_params = select_params_for_row(&mut params_selector, index)
            .map_err(|e| BacktestError::ValidationError(e.to_string()))?;
        let current_config = WriteConfig::from_params(current_params);

        state.current_index = index;
        state.prev_bar = state.current_bar;
        state.current_bar = current_bar;
        state.calculate_position(current_params);
        state.calculate_capital(current_params);
        row.write(&state, &current_config);
    }

    Ok(buffers)
}

/// 初始化输出缓冲区的第0行和第1行数据
#[inline(never)]
fn initialize_buffer_rows_0_and_1(
    buffers: &mut OutputBuffers,
    state: &mut BacktestState<'_>,
    prepared_data: &PreparedData<'_>,
    config: &WriteConfig,
) {
    // 第0行 (如果存在)
    if !prepared_data.time.is_empty() {
        state.current_index = 0;
        state.current_bar = CurrentBarData::new(prepared_data, 0);
        buffers.write_row(0, state, config);
    }

    // 第1行 (如果存在)
    if prepared_data.time.len() > 1 {
        state.current_index = 1;
        state.prev_bar = state.current_bar; // bar[0]
        state.current_bar = CurrentBarData::new(prepared_data, 1);
        buffers.write_row(1, state, config);
    }
}
