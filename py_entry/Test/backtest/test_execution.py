class TestExampleExecution:
    """测试example.py基本执行功能"""

    def test_example_runs(self, backtest_result, backtest_df):
        """测试example能否运行"""
        assert backtest_result is not None, "回测结果为空"
        assert len(backtest_result) > 0, "回测结果列表为空"

        assert backtest_df is not None, "没有回测数据"
        assert not backtest_df.is_empty(), "回测数据为空"

        print(f"✅ example运行成功: {len(backtest_df)} 行数据")
        print(f"📋 实际输出列: {backtest_df.columns}")
