from py_entry.trading_bot import (
    RuntimeChecks,
    StrategyParams,
    PositionStructure,
    BalanceStructure,
)
from .test_mocks import MockCallbacks


class TestOrphanOrderCheck:
    """孤儿订单检查测试"""

    def test_no_position_should_cancel(self):
        """无持仓时应该取消所有挂单"""
        mock = MockCallbacks()
        mock.positions = []  # 无持仓
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.orphan_order_check(params)

        assert result.success is True
        assert any(c["method"] == "cancel_all_orders" for c in mock.call_log)

    def test_has_position_should_not_cancel(self):
        """有持仓时不应该取消挂单"""
        mock = MockCallbacks()
        mock.positions = [
            PositionStructure(symbol="BTC/USDT", contracts=0.1, side="long")
        ]
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.orphan_order_check(params)

        assert result.success is True
        assert not any(c["method"] == "cancel_all_orders" for c in mock.call_log)


class TestDuplicateEntryCheck:
    """重复开仓检查测试"""

    def test_no_position_should_proceed(self):
        """无持仓时允许开仓"""
        mock = MockCallbacks()
        mock.positions = []
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.duplicate_entry_check(params, "long")

        assert result.success is True
        assert result.data == "proceed"

    def test_same_side_position_should_skip(self):
        """同向持仓时跳过开仓"""
        mock = MockCallbacks()
        mock.positions = [
            PositionStructure(symbol="BTC/USDT", contracts=0.1, side="long")
        ]
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.duplicate_entry_check(params, "long")

        assert result.success is True
        assert result.data == "skip"

    def test_opposite_side_position_should_skip(self):
        """反向持仓时跳过开仓"""
        mock = MockCallbacks()
        mock.positions = [
            PositionStructure(symbol="BTC/USDT", contracts=0.1, side="short")
        ]
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.duplicate_entry_check(params, "long")

        assert result.success is True
        assert result.data == "skip"


class TestMinOrderCheck:
    """最小订单检查测试"""

    def test_amount_below_min_should_fail(self):
        """数量低于最小值时检查失败"""
        mock = MockCallbacks()
        mock.market_info.min_amount = 0.01
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.min_order_check(params, amount=0.005, price=50000)

        assert result.success is True
        assert result.data == "fail"

    def test_amount_above_min_should_pass(self):
        """数量高于最小值时检查通过"""
        mock = MockCallbacks()
        mock.market_info.min_amount = 0.01
        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.min_order_check(params, amount=0.1, price=50000)

        assert result.success is True
        assert result.data == "pass"

    def test_amount_fallback_to_precision(self):
        """测试 min_amount 为 0 时回退使用 precision_amount"""
        mock = MockCallbacks()
        mock.market_info.min_amount = 0.0  # Missing/Zero
        mock.market_info.precision_amount = 0.001  # Should be used as threshold

        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        # Case 1: amount < precision_amount -> Fail
        result_fail = checks.min_order_check(params, amount=0.0005, price=50000)
        assert result_fail.success is True
        assert result_fail.data == "fail"

        # Case 2: amount >= precision_amount -> Pass
        result_pass = checks.min_order_check(params, amount=0.001, price=50000)
        assert result_pass.success is True
        assert result_pass.data == "pass"

    def test_invalid_precision_should_fail(self):
        """测试无效的 precision_amount 应导致 Fail-Fast"""
        mock = MockCallbacks()
        mock.market_info.min_amount = 0.0
        mock.market_info.precision_amount = 0.0  # Invalid!

        checks = RuntimeChecks(mock)
        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")

        result = checks.min_order_check(params, amount=0.1, price=50000)

        # 预期：直接报错 (success=False)
        assert result.success is False
        # 预期：直接报错 (success=False)
        assert result.success is False
        assert result.message is not None
        assert "Invalid precision_amount (<= 0)" in result.message


class TestOrderAmountCalculation:
    """订单数量计算测试"""

    def test_calculate_amount_step_size_one(self):
        """测试步长为 1.0 的情况 (替代原本的 Integer Precision)"""
        mock = MockCallbacks()
        # 余额 1000, 仓位 10%, 杠杆 5x -> 价值 500
        mock.balance = BalanceStructure(
            free={"USDT": 1000.0},
            used={"USDT": 0.0},
            total={"USDT": 1000.0},
        )
        # 注意：这里如果后端传3，意味着步长为3，而不是3位小数！
        # 这里模拟合法的 Step Size = 1.0
        mock.market_info.precision_amount = 1.0

        checks = RuntimeChecks(mock)
        params = StrategyParams(
            base_data_key="ohlcv_15m",
            symbol="BTC/USDT",
            position_size_pct=0.1,
            leverage=5,
            settlement_currency="USDT",
        )

        # 价格 49.38 -> Raw Amount 10.1255...
        # 10.125 / 1.0 = 10.125 -> floor -> 10.0 -> * 1.0 = 10.0
        result = checks.calculate_order_amount(params, entry_price=49.38)

        assert result.success is True
        assert result.data == 10.0

    def test_calculate_amount_float_step_size(self):
        """测试浮点步长 (Step Size) 模式 (e.g., 0.001)"""
        mock = MockCallbacks()
        # 余额 1000, 仓位 10%, 杠杆 5x -> 价值 500
        mock.balance = BalanceStructure(
            free={"USDT": 1000.0},
            used={"USDT": 0.0},
            total={"USDT": 1000.0},
        )
        mock.market_info.precision_amount = 0.001  # Float (Step Size)

        checks = RuntimeChecks(mock)
        params = StrategyParams(
            base_data_key="ohlcv_15m",
            symbol="BTC/USDT",
            position_size_pct=0.1,
            leverage=5,
            settlement_currency="USDT",
        )

        # 价格 49.38 -> Raw Amount 10.1255569... -> expected 10.125
        result = checks.calculate_order_amount(params, entry_price=49.38)

        assert result.success is True
        assert result.success is True
        assert result.data is not None
        assert abs(result.data - 10.125) < 1e-10

    def test_calculate_amount_large_step_size(self):
        """测试大步长模式 (e.g., 0.5)"""
        mock = MockCallbacks()
        mock.balance = BalanceStructure(
            free={"USDT": 1000.0},
            used={"USDT": 0.0},
            total={"USDT": 1000.0},
        )
        mock.market_info.precision_amount = 0.5  # Float (Step Size)

        checks = RuntimeChecks(mock)
        params = StrategyParams(
            base_data_key="ohlcv_15m",
            symbol="BTC/USDT",
            position_size_pct=0.1,
            leverage=5,
            settlement_currency="USDT",
        )

        # 价格 49.38 -> Raw Amount 10.1255...
        # 10.125 / 0.5 = 20.25 -> floor -> 20 -> 20 * 0.5 = 10.0
        result = checks.calculate_order_amount(params, entry_price=49.38)

        assert result.success is True
        assert result.data == 10.0

    def test_calculate_amount_invalid_precision_cleanup(self):
        """测试无效精度回退到原始值"""
        mock = MockCallbacks()
        mock.balance = BalanceStructure(
            free={"USDT": 1000.0},
            used={"USDT": 0.0},
            total={"USDT": 1000.0},
        )
        mock.market_info.precision_amount = "invalid"  # type: ignore

        checks = RuntimeChecks(mock)
        params = StrategyParams(
            base_data_key="ohlcv_15m",
            symbol="BTC/USDT",
            position_size_pct=0.1,
            leverage=5,
            settlement_currency="USDT",
        )

        # Raw Amount = 500 / 50 = 10.0
        result = checks.calculate_order_amount(params, entry_price=50.0)

        assert result.success is True
        assert result.data == 10.0
