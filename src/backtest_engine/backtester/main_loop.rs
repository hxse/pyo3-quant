use super::data_preparer::PreparedData;
use super::output::OutputBuffers;
use super::state::BacktestState;
use crate::data_conversion::BacktestParams;
use crate::error::backtest_error::BacktestError;
use polars::prelude::Series;

/// 运行回测主循环
///
/// # 参数
/// * `prepared_data` - 准备好的回测数据
/// * `state` - 可变的回测状态引用
/// * `buffers` - 拥有的输出缓冲区
///
/// # 返回
/// 更新后的输出缓冲区
pub fn run_main_loop(
    prepared_data: &PreparedData,
    state: &mut BacktestState,
    mut buffers: OutputBuffers,
    atr_series: &Option<Series>,
    backtest_params: &BacktestParams,
) -> Result<OutputBuffers, BacktestError> {
    let data_length = prepared_data.time.len();

    // 如果数据长度小于等于0，直接返回空的OutputBuffers
    if data_length <= 0 {
        return Ok(buffers);
    }

    // 在循环前断言所有切片的长度，帮助编译器优化掉边界检查
    assert_eq!(prepared_data.open.len(), data_length);
    assert_eq!(prepared_data.high.len(), data_length);
    assert_eq!(prepared_data.low.len(), data_length);
    assert_eq!(prepared_data.close.len(), data_length);
    assert_eq!(prepared_data.volume.len(), data_length);
    assert_eq!(prepared_data.enter_long.len(), data_length);
    assert_eq!(prepared_data.exit_long.len(), data_length);
    assert_eq!(prepared_data.enter_short.len(), data_length);
    assert_eq!(prepared_data.exit_short.len(), data_length);

    // 初始化阶段：给OutputBuffers每个数组push一个默认值
    // 建议OutputBuffers用push更新, 因为性能高
    buffers.push_default_value();

    // 如果数据长度大于1，进入主循环
    if data_length > 1 {
        // 主循环从1开始，因为已经初始化过了
        for i in 1..data_length {
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

            // 给OutputBuffers每个数组push一个默认值
            buffers.push_default_value();
        }
    }

    // 验证所有数组的长度是否相等
    buffers.validate_array_lengths()?;

    Ok(buffers)
}
