use super::state::{current_bar_data::CurrentBarData, BacktestState};
use super::{data_preparer::PreparedData, output::OutputBuffers};
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

    // ---------- 3. 初始化第0行数据 ----------
    // 将 backtest_state 的初始值写入到 buffers 的第0行
    initialize_buffer_row_zero(&mut buffers, state);

    // ---------- 4. 主循环 ----------
    // 索引 0 已经正确初始化
    if data_length > 1 {
        for i in 1..data_length {
            state.current_bar = CurrentBarData::new(prepared_data, i);
            state.prev_bar = CurrentBarData::new(prepared_data, i - 1);
            // 从 i >= 2 开始才有 prev_prev_bar
            if i >= 2 {
                state.prev_prev_bar = CurrentBarData::new(prepared_data, i - 2);
            }

            if state.should_skip_current_bar() {
                state.reset_position_on_skip();
                state.reset_capital_on_skip();
            } else {
                // 使用状态机方法计算新的仓位状态（内部已更新状态）
                state.calculate_position(backtest_params);

                state.calculate_capital(backtest_params);
            }

            // 使用工具函数更新当前行数据
            update_buffer_row(&mut buffers, state, i);
        }
    }

    // 统一处理 ATR 数据赋值（移到主循环外）
    // 直接克隆整个 Vec，避免循环中的逐个赋值
    if let Some(ref atr_data) = prepared_data.atr {
        buffers.atr = Some(atr_data.clone());
    }

    Ok(buffers)
}

/// 更新输出缓冲区指定行的数据
///
/// 将 backtest_state 的当前值写入到 buffers 的指定行
/// 更新输出缓冲区的单行数据
///
/// 将当前回测状态写入输出缓冲区的指定行
fn update_buffer_row(buffers: &mut OutputBuffers, state: &BacktestState, row_index: usize) {
    // === 资金状态 ===
    buffers.balance[row_index] = state.capital_state.balance;
    buffers.equity[row_index] = state.capital_state.equity;
    buffers.trade_pnl_pct[row_index] = state.capital_state.trade_pnl_pct;
    buffers.total_return_pct[row_index] = state.capital_state.total_return_pct;
    buffers.fee[row_index] = state.capital_state.fee;
    buffers.fee_cum[row_index] = state.capital_state.fee_cum;
    buffers.current_drawdown[row_index] = state.capital_state.current_drawdown;

    // === 价格列（价格驱动状态的核心） ===
    buffers.entry_long_price[row_index] = state.action.entry_long_price.unwrap_or(f64::NAN);
    buffers.entry_short_price[row_index] = state.action.entry_short_price.unwrap_or(f64::NAN);
    buffers.exit_long_price[row_index] = state.action.exit_long_price.unwrap_or(f64::NAN);
    buffers.exit_short_price[row_index] = state.action.exit_short_price.unwrap_or(f64::NAN);

    // === 风险价格（可选列） ===
    if let Some(ref mut sl_pct_price_long) = buffers.sl_pct_price_long {
        sl_pct_price_long[row_index] = state.risk_state.sl_pct_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut sl_pct_price_short) = buffers.sl_pct_price_short {
        sl_pct_price_short[row_index] = state.risk_state.sl_pct_price_short.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tp_pct_price_long) = buffers.tp_pct_price_long {
        tp_pct_price_long[row_index] = state.risk_state.tp_pct_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tp_pct_price_short) = buffers.tp_pct_price_short {
        tp_pct_price_short[row_index] = state.risk_state.tp_pct_price_short.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tsl_pct_price_long) = buffers.tsl_pct_price_long {
        tsl_pct_price_long[row_index] = state.risk_state.tsl_pct_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tsl_pct_price_short) = buffers.tsl_pct_price_short {
        tsl_pct_price_short[row_index] = state.risk_state.tsl_pct_price_short.unwrap_or(f64::NAN);
    }
    if let Some(ref mut sl_atr_price_long) = buffers.sl_atr_price_long {
        sl_atr_price_long[row_index] = state.risk_state.sl_atr_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut sl_atr_price_short) = buffers.sl_atr_price_short {
        sl_atr_price_short[row_index] = state.risk_state.sl_atr_price_short.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tp_atr_price_long) = buffers.tp_atr_price_long {
        tp_atr_price_long[row_index] = state.risk_state.tp_atr_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tp_atr_price_short) = buffers.tp_atr_price_short {
        tp_atr_price_short[row_index] = state.risk_state.tp_atr_price_short.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tsl_atr_price_long) = buffers.tsl_atr_price_long {
        tsl_atr_price_long[row_index] = state.risk_state.tsl_atr_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tsl_atr_price_short) = buffers.tsl_atr_price_short {
        tsl_atr_price_short[row_index] = state.risk_state.tsl_atr_price_short.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tsl_psar_price_long) = buffers.tsl_psar_price_long {
        tsl_psar_price_long[row_index] = state.risk_state.tsl_psar_price_long.unwrap_or(f64::NAN);
    }
    if let Some(ref mut tsl_psar_price_short) = buffers.tsl_psar_price_short {
        tsl_psar_price_short[row_index] = state.risk_state.tsl_psar_price_short.unwrap_or(f64::NAN);
    }

    // === Risk State Output ===
    buffers.risk_in_bar_direction[row_index] = state.risk_state.in_bar_direction;
    buffers.first_entry_side[row_index] = state.action.first_entry_side;
}

/// 初始化输出缓冲区的第0行数据
///
/// 将 backtest_state 的初始值写入到 buffers 的第0行，确保初始状态正确
fn initialize_buffer_row_zero(buffers: &mut OutputBuffers, state: &BacktestState) {
    update_buffer_row(buffers, state, 0);
}
