import pytest
import pyo3_quant
from py_entry.trading_bot.signal import SignalState  # Pydantic Model

resolve_actions = pyo3_quant.backtest_engine.action_resolver.resolve_actions


def parse_signal_rs(row: dict, symbol: str, sl: bool, tp: bool) -> SignalState:
    """包装函数：Rust Dict -> Pydantic Model"""
    raw_dict = resolve_actions(row, symbol, sl, tp)
    # Rust 返回的是 {"actions": [...], "has_exit": ...}
    # Pydantic 会自动验证嵌套的 actions
    return SignalState.model_validate(raw_dict)


class TestActionResolver:
    def test_long_entry(self):
        row = {
            "frame_state": 2.0,  # hold_long_first
            "entry_long_price": 50000.0,
            "sl_pct_price_long": 49000.0,
        }
        # 使用 Pydantic Model 接收
        state = parse_signal_rs(row, "BTC/USDT", True, False)

        assert isinstance(state, SignalState)
        assert state.has_exit is False
        assert len(state.actions) == 2
        assert state.actions[0].action_type == "create_limit_order"
        assert state.actions[0].symbol == "BTC/USDT"
        assert state.actions[0].side == "long"
        assert state.actions[0].price == 50000.0

        assert state.actions[1].action_type == "create_stop_market_order"
        assert state.actions[1].price == 49000.0

    def test_reversal_long_to_short(self):
        row = {
            "frame_state": 11.0,  # reversal_L_to_S
            "entry_short_price": 48000.0,
        }
        state = parse_signal_rs(row, "BTC/USDT", True, False)

        assert state.has_exit is True
        # 顺序: close -> cancel -> entry
        assert len(state.actions) == 3
        assert state.actions[0].action_type == "close_position"
        assert state.actions[1].action_type == "cancel_all_orders"
        assert state.actions[2].action_type == "create_limit_order"
        assert state.actions[2].side == "short"

    def test_next_bar_exit(self):
        row = {
            "frame_state": 5.0,  # exit_long_signal
        }
        state = parse_signal_rs(row, "BTC/USDT", True, False)

        assert state.has_exit is True
        assert len(state.actions) == 2
        assert state.actions[0].action_type == "close_position"
        assert state.actions[1].action_type == "cancel_all_orders"

    def test_in_bar_exit(self):
        row = {
            "frame_state": 6.0,  # exit_long_risk
        }
        state = parse_signal_rs(row, "BTC/USDT", True, False)

        assert state.has_exit is True
        # In-bar 离场由止损/止盈单自动触发，无需代码生成 close_position 动作
        assert len(state.actions) == 0

    def test_add_all_sl_tp_orders_for_same_side(self):
        row = {
            "frame_state": 2.0,  # hold_long_first
            "entry_long_price": 50000.0,
            "sl_pct_price_long": 49500.0,
            "sl_atr_price_long": 49200.0,
            "tp_pct_price_long": 50500.0,
            "tp_atr_price_long": 50800.0,
        }
        state = parse_signal_rs(row, "BTC/USDT", True, True)

        assert state.has_exit is False
        # 顺序：entry + 2 个 SL + 2 个 TP
        assert len(state.actions) == 5
        assert state.actions[0].action_type == "create_limit_order"

        sl_actions = [
            action
            for action in state.actions
            if action.action_type == "create_stop_market_order"
        ]
        assert len(sl_actions) == 2
        assert {action.price for action in sl_actions} == {49500.0, 49200.0}

        tp_actions = [
            action
            for action in state.actions
            if action.action_type == "create_take_profit_market_order"
        ]
        assert len(tp_actions) == 2
        assert {action.price for action in tp_actions} == {50500.0, 50800.0}
