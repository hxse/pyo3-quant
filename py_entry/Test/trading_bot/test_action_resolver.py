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
            "first_entry_side": 1.0,
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
            "first_entry_side": -1.0,
            "exit_long_price": 50000.0,
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
            "first_entry_side": 0.0,
            "exit_long_price": 51000.0,
            "risk_in_bar_direction": 0.0,
        }
        state = parse_signal_rs(row, "BTC/USDT", True, False)

        assert state.has_exit is True
        assert len(state.actions) == 2
        assert state.actions[0].action_type == "close_position"
        assert state.actions[1].action_type == "cancel_all_orders"

    def test_in_bar_exit(self):
        row = {
            "exit_long_price": 51000.0,
            "risk_in_bar_direction": 1.0,
        }
        state = parse_signal_rs(row, "BTC/USDT", True, False)

        assert state.has_exit is True
        # In-bar 离场由止损/止盈单自动触发，无需代码生成 close_position 动作
        assert len(state.actions) == 0
