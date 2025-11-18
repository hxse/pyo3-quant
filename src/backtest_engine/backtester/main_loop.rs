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
            state.current_bar = CurrentBarData::new(prepared_data, i);

            if state.should_skip_current_bar() {
                continue;
            }

            // 使用状态机方法计算新的仓位状态（内部已更新状态）
            state.calculate_position(backtest_params);

            state.calculate_capital(backtest_params);

            // 直接索引写入（边界检查已消除）
            buffers.current_position[i] = state.action.current_position.as_i8();
            buffers.entry_long_price[i] = state.action.entry_long_price.unwrap_or(f64::NAN);
            buffers.entry_short_price[i] = state.action.entry_short_price.unwrap_or(f64::NAN);
            buffers.exit_long_price[i] = state.action.exit_long_price.unwrap_or(f64::NAN);
            buffers.exit_short_price[i] = state.action.exit_short_price.unwrap_or(f64::NAN);

            if let Some(ref mut sl_pct_price) = buffers.sl_pct_price {
                sl_pct_price[i] = state.risk_state.sl_pct_price.unwrap_or(f64::NAN);
            }
            if let Some(ref mut tp_pct_price) = buffers.tp_pct_price {
                tp_pct_price[i] = state.risk_state.tp_pct_price.unwrap_or(f64::NAN);
            }
            if let Some(ref mut tsl_pct_price) = buffers.tsl_pct_price {
                tsl_pct_price[i] = state.risk_state.tsl_pct_price.unwrap_or(f64::NAN);
            }
            if let Some(ref mut sl_atr_price) = buffers.sl_atr_price {
                sl_atr_price[i] = state.risk_state.sl_atr_price.unwrap_or(f64::NAN);
            }
            if let Some(ref mut tp_atr_price) = buffers.tp_atr_price {
                tp_atr_price[i] = state.risk_state.tp_atr_price.unwrap_or(f64::NAN);
            }
            if let Some(ref mut tsl_atr_price) = buffers.tsl_atr_price {
                tsl_atr_price[i] = state.risk_state.tsl_atr_price.unwrap_or(f64::NAN);
            }

            buffers.balance[i] = state.capital_state.balance;
            buffers.equity[i] = state.capital_state.equity;
            buffers.trade_pnl_pct[i] = state.capital_state.trade_pnl_pct;
            buffers.total_return_pct[i] = state.capital_state.total_return_pct;
            buffers.fee[i] = state.capital_state.fee;
            buffers.fee_cum[i] = state.capital_state.fee_cum;
            buffers.peak_equity[i] = state.capital_state.peak_equity;
        }
    }

    // 统一处理 ATR 数据赋值（移到主循环外）
    // 直接克隆整个 Vec，避免循环中的逐个赋值
    if let Some(ref atr_data) = prepared_data.atr {
        buffers.atr = Some(atr_data.clone());
    }

    Ok(buffers)
}
