import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from py_entry.trading_bot import (
    CallbackResult,
    PositionsResponse,
    CancelAllOrdersResponse,
    LimitOrderRequest,
    MarketOrderRequest,
    CancelAllOrdersRequest,
    OptimizationCallbacks,
    TradingBot,
    StrategyParams,
    Callbacks,
)


class TestOptimizationCallbacks:
    """测试优化代理逻辑"""

    @pytest.fixture
    def mock_inner(self):
        """Mock 内部回调"""
        mock = MagicMock(spec=Callbacks)
        # 默认返回成功
        mock.fetch_positions.return_value = CallbackResult(
            success=True, data=PositionsResponse(positions=[])
        )
        mock.create_limit_order.return_value = CallbackResult(success=True)
        mock.create_market_order.return_value = CallbackResult(success=True)
        mock.create_stop_market_order.return_value = CallbackResult(success=True)
        mock.create_take_profit_market_order.return_value = CallbackResult(success=True)
        mock.close_position.return_value = CallbackResult(success=True)
        mock.cancel_all_orders.return_value = CallbackResult(
            success=True, data=CancelAllOrdersResponse(result=[])
        )
        return mock

    def test_fetch_positions_caching(self, mock_inner):
        """测试 fetch_positions 缓存命中"""
        proxy = OptimizationCallbacks(mock_inner, symbol="BTC/USDT")

        # 第一次调用
        proxy.fetch_positions("binance", "future", "live", ["BTC/USDT"])
        assert mock_inner.fetch_positions.call_count == 1

        # 第二次调用（相同 symbol） -> 应该命中缓存
        proxy.fetch_positions("binance", "future", "live", ["BTC/USDT"])
        assert mock_inner.fetch_positions.call_count == 1

        # 第三次调用（不同 symbol） -> 不命中缓存
        proxy.fetch_positions("binance", "future", "live", ["ETH/USDT"])
        assert mock_inner.fetch_positions.call_count == 2

    def test_invalidation_limit_order(self, mock_inner):
        """测试 create_limit_order 导致缓存失效 + strict 重置"""
        proxy = OptimizationCallbacks(mock_inner, symbol="BTC/USDT")

        # 填充缓存
        proxy.fetch_positions("binance", "future", "live", ["BTC/USDT"])
        proxy.cancel_all_orders(
            CancelAllOrdersRequest(
                exchange_name="binance", market="future", symbol="BTC/USDT"
            )
        )  # Set cancelled_all = True

        assert proxy._positions_cache is not None
        assert proxy._cancelled_all is True

        # 下限价单
        req = LimitOrderRequest(
            exchange_name="binance",
            market="future",
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
            price=100.0,
        )
        proxy.create_limit_order(req)

        # 验证：缓存失效，cancelled_all 重置
        assert proxy._positions_cache is None
        assert proxy._cancelled_all is False

    def test_invalidation_market_order(self, mock_inner):
        """测试 create_market_order 仅缓存失效，cancelled_all 不重置"""
        proxy = OptimizationCallbacks(mock_inner, symbol="BTC/USDT")

        # 填充
        proxy.fetch_positions("binance", "future", "live", ["BTC/USDT"])
        proxy.cancel_all_orders(
            CancelAllOrdersRequest(
                exchange_name="binance", market="future", symbol="BTC/USDT"
            )
        )

        assert proxy._positions_cache is not None
        assert proxy._cancelled_all is True

        # 下市价单
        req = MarketOrderRequest(
            exchange_name="binance",
            market="future",
            symbol="BTC/USDT",
            side="buy",
            amount=1.0,
        )
        proxy.create_market_order(req)

        # 验证：缓存失效
        assert proxy._positions_cache is None
        # 验证：cancelled_all 保持不变（因为市价单不挂单）
        assert proxy._cancelled_all is True

    def test_cancel_all_orders_dedup(self, mock_inner):
        """测试 cancel_all_orders 去重"""
        proxy = OptimizationCallbacks(mock_inner, symbol="BTC/USDT")
        req = CancelAllOrdersRequest(
            exchange_name="binance", market="future", symbol="BTC/USDT"
        )

        # 第一次取消
        proxy.cancel_all_orders(req)
        assert mock_inner.cancel_all_orders.call_count == 1
        assert proxy._cancelled_all is True

        # 第二次取消 -> 应该被去重
        proxy.cancel_all_orders(req)
        assert mock_inner.cancel_all_orders.call_count == 1

        # 对其他 symbol 取消 -> 不去重
        req_eth = CancelAllOrdersRequest(
            exchange_name="binance", market="future", symbol="ETH/USDT"
        )
        proxy.cancel_all_orders(req_eth)
        assert mock_inner.cancel_all_orders.call_count == 2


class TestTimeframeParsing:
    """测试 Timeframe 解析修复"""

    def test_parse_logic(self):
        """直接测试 bot._parse_period_minutes 逻辑或 _process_symbol 传参"""
        # 由于 _process_symbol 内部直接 split，我们通过 mock fetch_ohlcv 来验证
        mock_cb = MagicMock(spec=Callbacks)
        mock_cb.fetch_ohlcv.return_value = CallbackResult(success=True, data=[])
        mock_cb.get_strategy_params.return_value = CallbackResult(success=True, data=[])

        bot = TradingBot(callbacks=mock_cb)

        # 构造一个特殊的 base_data_key
        params = StrategyParams(base_data_key="trade_1h", symbol="BTC/USDT")

        # 调用 private method _process_symbol 进行测试（或者 run_cycle）
        # 这里为了简单直接调 _process_symbol
        import asyncio

        asyncio.run(bot._process_symbol(params))

        # 验证 fetch_ohlcv 收到的 timeframe 参数
        # 之前的逻辑 replace('ohlcv_', '') 会导致 'trade_1h' -> 'trade_1h'
        # 修复后的逻辑 split('_')[-1] 应该 -> '1h'
        call_args = mock_cb.fetch_ohlcv.call_args
        assert call_args is not None
        _, kwargs = call_args

        assert kwargs["timeframe"] == "1h"

    def test_is_new_period_should_respect_large_timeframe_bucket(self):
        """4h/1d 周期必须按时间桶判定，不能每小时都触发。"""
        mock_cb = MagicMock(spec=Callbacks)
        bot = TradingBot(
            callbacks=mock_cb,
            time_func=lambda: datetime(2026, 2, 16, 1, 0, 3, tzinfo=timezone.utc),
        )

        params_4h = StrategyParams(base_data_key="trade_4h", symbol="BTC/USDT")
        params_1d = StrategyParams(base_data_key="trade_1d", symbol="BTC/USDT")

        assert bot.is_new_period(params_4h) is False
        assert bot.is_new_period(params_1d) is False

        aligned_bot = TradingBot(
            callbacks=mock_cb,
            time_func=lambda: datetime(2026, 2, 16, 4, 0, 3, tzinfo=timezone.utc),
        )
        assert aligned_bot.is_new_period(params_4h) is True
