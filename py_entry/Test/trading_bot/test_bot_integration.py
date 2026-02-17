import pytest
from py_entry.trading_bot import (
    TradingBot,
    BotConfig,
    StrategyParams,
    SignalState,
    SignalAction,
)
from .test_mocks import MockCallbacks
from py_entry.trading_bot.models import PositionStructure


class TestEntryFlow:
    """进场流程集成测试"""

    def test_long_entry_flow(self):
        """多头进场完整流程"""
        mock = MockCallbacks()
        bot = TradingBot(callbacks=mock, config=BotConfig(entry_order_type="limit"))
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        signal = SignalState(
            actions=[
                SignalAction(
                    action_type="create_limit_order",
                    symbol="BTC/USDT",
                    side="long",
                    price=50000.0,
                ),
                SignalAction(
                    action_type="create_stop_market_order",
                    symbol="BTC/USDT",
                    side="long",
                    price=49000.0,
                ),
            ],
            has_exit=False,
        )

        result = bot.run_single_step(params, signal=signal)

        assert result.success is True
        # 验证调用序列
        methods = [c["method"] for c in mock.call_log]
        assert "fetch_positions" in methods  # 重复开仓检查
        assert "fetch_balance" in methods  # 余额查询
        assert "create_limit_order" in methods  # 下单
        assert "create_stop_market_order" in methods  # 挂 SL


class TestExitFlow:
    """离场流程集成测试"""

    def test_exit_flow(self):
        """离场完整流程"""
        mock = MockCallbacks()
        bot = TradingBot(callbacks=mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        signal = SignalState(
            actions=[
                SignalAction(action_type="close_position", symbol="BTC/USDT"),
                SignalAction(action_type="cancel_all_orders", symbol="BTC/USDT"),
            ],
            has_exit=True,
        )

        result = bot.run_single_step(params, signal=signal)

        assert result.success is True
        methods = [c["method"] for c in mock.call_log]
        assert "close_position" in methods
        assert "cancel_all_orders" in methods

    def test_reversal_should_not_be_short_circuited_by_duplicate_entry_check(self):
        """反手信号不应被重复开仓检查提前短路。"""
        mock = MockCallbacks()
        # 当前有多头仓位，信号要反手做空。
        mock.positions = [
            PositionStructure(symbol="BTC/USDT", contracts=0.1, side="long")
        ]

        bot = TradingBot(callbacks=mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")
        signal = SignalState(
            actions=[
                SignalAction(action_type="close_position", symbol="BTC/USDT"),
                SignalAction(action_type="cancel_all_orders", symbol="BTC/USDT"),
                SignalAction(
                    action_type="create_limit_order",
                    symbol="BTC/USDT",
                    side="short",
                    price=48000.0,
                ),
            ],
            has_exit=True,
        )

        result = bot.run_single_step(params, signal=signal)
        assert result.success is True

        methods = [c["method"] for c in mock.call_log]
        assert "close_position" in methods
        assert "cancel_all_orders" in methods
        assert "create_limit_order" in methods


class TestFailFast:
    """Fail-Fast 测试"""

    def test_fetch_positions_failure_should_stop(self):
        """fetch_positions 失败应终止本轮"""
        mock = MockCallbacks()

        # 让 fetch_positions 失败
        original_fetch = mock.fetch_positions

        def failing_fetch(exchange_name, market, mode, symbols):
            from py_entry.trading_bot import CallbackResult

            return CallbackResult(success=False, message="Network error")

        mock.fetch_positions = failing_fetch  # type: ignore

        bot = TradingBot(callbacks=mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        signal = SignalState(
            actions=[
                SignalAction(
                    action_type="create_limit_order",
                    symbol="BTC/USDT",
                    side="long",
                    price=50000.0,
                ),
            ],
            has_exit=False,
        )

        result = bot.run_single_step(params, signal=signal)

        assert result.success is False
        # 验证没有下单
        assert not any(c["method"] == "create_limit_order" for c in mock.call_log)


class TestCustomSettlement:
    """自定义结算币种测试"""

    def test_btc_settlement(self):
        """测试使用 BTC 作为结算币种"""
        mock = MockCallbacks()

        # 修改 Mock 余额：USDT=0, BTC=1.0
        mock.balance.free = {"USDT": 0.0, "BTC": 1.0}

        # 策略参数指定结算币种为 BTC
        params = StrategyParams(
            base_data_key="ohlcv_15m",
            symbol="ETH/BTC",
            settlement_currency="BTC",
            position_size_pct=0.1,  # 0.1 BTC
        )

        bot = TradingBot(callbacks=mock)
        signal = SignalState(
            actions=[
                SignalAction(
                    action_type="create_limit_order",
                    symbol="ETH/BTC",
                    side="long",
                    price=0.05,  # ETH/BTC Price
                )
            ]
        )

        result = bot.run_single_step(params, signal=signal)

        assert result.success is True

        # 验证是否正确计算了数量
        # 余额 1.0 BTC * 0.1 / 0.05 = 2.0 ETH
        limit_orders = [c for c in mock.call_log if c["method"] == "create_limit_order"]
        assert len(limit_orders) == 1
        order_req = limit_orders[0][
            "request"
        ]  # limit_orders[0] is dict with "request": request_dict

        # 由于 MockCallbacks._log 记录的是 request.model_dump()
        # "create_limit_order", request=request.model_dump()
        # 所以 limit_orders[0] 是 {"method": "create_limit_order", "request": {...}}

        assert order_req["amount"] == 2.0


class TestOrderTypeOverride:
    """测试 entry_order_type 配置覆盖逻辑"""

    def test_limit_config_with_limit_signal(self):
        """配置 Limit，信号 Limit -> 执行 Limit"""
        mock = MockCallbacks()
        bot = TradingBot(callbacks=mock, config=BotConfig(entry_order_type="limit"))
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        signal = SignalState(
            actions=[
                SignalAction(
                    action_type="create_limit_order",
                    symbol="BTC/USDT",
                    side="long",
                    price=50000.0,
                )
            ]
        )

        result = bot.run_single_step(params, signal=signal)
        assert result.success is True

        methods = [c["method"] for c in mock.call_log]
        assert "create_limit_order" in methods
        assert "create_market_order" not in methods

    def test_market_config_with_limit_signal(self):
        """配置 Market，信号 Limit -> 覆盖为 Market"""
        mock = MockCallbacks()
        bot = TradingBot(callbacks=mock, config=BotConfig(entry_order_type="market"))
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        signal = SignalState(
            actions=[
                SignalAction(
                    action_type="create_limit_order",  # 原始信号是 Limit
                    symbol="BTC/USDT",
                    side="long",
                    price=50000.0,
                )
            ]
        )

        result = bot.run_single_step(params, signal=signal)
        assert result.success is True

        methods = [c["method"] for c in mock.call_log]
        # 验证原来的 limit order 被转成了 market order
        assert "create_market_order" in methods
        assert "create_limit_order" not in methods

    def test_limit_config_with_market_signal_fail(self):
        """配置 Limit，信号 Market (无价格) -> 跳过 (Error)"""
        mock = MockCallbacks()
        bot = TradingBot(callbacks=mock, config=BotConfig(entry_order_type="limit"))
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        signal = SignalState(
            actions=[
                SignalAction(
                    action_type="create_market_order",  # 信号是 Market
                    symbol="BTC/USDT",
                    side="long",
                    # price is None
                )
            ]
        )

        result = bot.run_single_step(params, signal=signal)

        # 因为代码中是 return CallbackResult(success=True) 并记录 error log 来跳过
        assert result.success is True

        methods = [c["method"] for c in mock.call_log]
        # 应该没有任何下单动作
        assert "create_limit_order" not in methods
        assert "create_market_order" not in methods
