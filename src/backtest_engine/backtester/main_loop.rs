use super::data_preparer::PreparedData;
use super::output::OutputBuffers;
use super::state::{current_bar_data::CurrentBarData, BacktestState};
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
            let current_bar = CurrentBarData::new(prepared_data, i);

            // 使用状态机方法计算新的仓位状态（内部已更新状态）
            state.calculate_position(backtest_params, current_bar);

            // 直接索引写入（边界检查已消除）
            buffers.position[i] = state.position.as_i8();
        }
    }

    Ok(buffers)
}
