import unittest
import pandas as pd
import numpy as np
from py_entry.scanner.indicators import (
    is_opening_bar,
    calculate_ema,
    calculate_macd,
    calculate_cci,
    is_cross_above,
    is_cross_below,
)


class TestIndicators(unittest.TestCase):
    def test_calculate_ema_basic(self):
        close = pd.Series([1, 2, 3, 4, 5] * 10)  # 50 data points
        ema = calculate_ema(close, period=10)
        self.assertEqual(len(ema), 50)
        self.assertFalse(ema.empty)
        # Check last value approximately
        # EMA(10) of steady stream
        self.assertIsInstance(ema.iloc[-1], float)

    def test_calculate_ema_not_enough_data(self):
        close = pd.Series([1, 2])
        # period > len(close) returns None in pandas-ta, so we get empty Series
        ema = calculate_ema(close, period=5)
        self.assertEqual(len(ema), 0)

    def test_calculate_macd_basic(self):
        close = pd.Series(np.random.randn(100) + 100)
        macd, signal, hist = calculate_macd(close)
        self.assertEqual(len(macd), 100)
        self.assertEqual(len(signal), 100)
        self.assertEqual(len(hist), 100)

    def test_calculate_macd_empty(self):
        close = pd.Series([], dtype=float)
        macd, signal, hist = calculate_macd(close)
        self.assertTrue(macd.empty)

    def test_calculate_cci_basic(self):
        high = pd.Series(np.random.randn(50) + 100)
        low = pd.Series(np.random.randn(50) + 90)
        close = pd.Series(np.random.randn(50) + 95)
        cci = calculate_cci(high, low, close, period=14)
        self.assertEqual(len(cci), 50)

    def test_is_cross_above_success(self):
        # We need [-2] (last completed) > 100 and [-3] <= 100
        # Data: [98, 102, 105]
        # [-1]=105 (forming), [-2]=102 (curr), [-3]=98 (prev)
        series = pd.Series([98, 102, 105])
        self.assertTrue(is_cross_above(series, 100))

    def test_is_cross_above_no_cross(self):
        # We need check if it did NOT cross in last completed bar
        # Data: [101, 102, 103]
        # [-2]=102 (>100), [-3]=101 (>100). Already above.
        series = pd.Series([101, 102, 103])
        self.assertFalse(is_cross_above(series, 100))

    def test_is_cross_above_with_series_threshold(self):
        # Series A: 10, 20, 30, 40
        # Series B: 15, 25, 25, 25
        # Index [-3] (1): A=20, B=25. A <= B.
        # Index [-2] (2): A=30, B=25. A > B. -> Cross Above
        # Index [-1] (3): forming
        s1 = pd.Series([10, 20, 30, 40])
        s2 = pd.Series([15, 25, 25, 25])
        self.assertTrue(is_cross_above(s1, s2))

    def test_is_cross_below_success(self):
        # Need [-2] < 100 and [-3] >= 100
        # Data: [102, 98, 90]
        # [-2]=98 (<100), [-3]=102 (>=100)
        series = pd.Series([102, 98, 90])
        self.assertTrue(is_cross_below(series, 100))


class TestIsOpeningBar(unittest.TestCase):
    def test_opening_bar_datetime_objects(self):
        """Test with pandas Timestamp objects (standard case)"""
        # Create a gap: 9:00, 9:05, 10:30 (Break > 5m)
        times = [
            pd.Timestamp("2023-01-01 09:00:00"),
            pd.Timestamp("2023-01-01 09:05:00"),
            pd.Timestamp("2023-01-01 10:30:00"),  # Gap here
            pd.Timestamp("2023-01-01 10:35:00"),
        ]
        df = pd.DataFrame({"datetime": times, "close": [1, 2, 3, 4]})

        # Determine duration: 5 minutes = 300 seconds
        duration = 300

        # Check at index 2 (10:30), prev is 09:05. Gap = 1h 25m >> 300s.
        # Function checks [-2] vs [-3].
        # So if we pass the whole DF, iloc[-2] is 10:30, iloc[-3] is 09:05.
        # Wait, if pass whole DF (len=4): [-1]=10:35 (forming), [-2]=10:30 (last completed), [-3]=09:05.
        # Gap between [-2] and [-3] is huge. Should be True.

        # Test case 1: Huge gap
        self.assertTrue(is_opening_bar(df, duration))

        # Test case 2: Normal gap (5 mins)
        # Slice first 2 elements. [-1]=09:05 (forming?), [-2]=09:00.
        # But wait, checking [-2] and [-3] requires at least 3 elements.
        df_short = df.iloc[:3]  # 09:00, 09:05, 10:30.
        # [-1]=10:30, [-2]=09:05, [-3]=09:00.
        # Gap between 09:05 and 09:00 is 5 mins = duration. Not > 2*duration.
        self.assertFalse(is_opening_bar(df_short, duration))

    def test_opening_bar_int64_nanoseconds(self):
        """Test with int64 nanoseconds (simulating TqSdk)"""
        # 1 second = 1e9 ns
        base = 1600000000 * 10**9
        duration = 5  # 5 seconds

        # Case: T0, T1 (gap 5s), T2 (gap 20s), T3 (gap 5s)
        # Times: 0, 5, 30, 35
        times_ns = np.array([0, 5, 30, 35], dtype="int64") * 10**9 + base

        df = pd.DataFrame({"datetime": times_ns, "close": [1, 2, 3, 4]})

        # Check full DF: [-2]=30s, [-3]=5s. Gap=25s. Duration=5s. Gap > 2*5. True.
        self.assertTrue(is_opening_bar(df, duration))

        # Check subset: T0, T1, T2. [-2]=T1(5s), [-3]=T0(0s). Gap=5s. False.
        self.assertFalse(is_opening_bar(df.iloc[:3], duration))

    def test_opening_bar_float_timestamps(self):
        """Test with float nanoseconds (since implementation divides by 1e9)"""
        duration = 60
        # 1e9 multiplier to satisfy the assumption that numbers are ns
        # Use a realistic timestamp (2023) to satisfy the sanity check (> 1e18)
        base = 1700000000 * 1e9

        times = [base, base + 60 * 1e9, base + 600 * 1e9, base + 660 * 1e9]
        df = pd.DataFrame({"datetime": times, "close": [1, 1, 1, 1]})

        # [-2] = 600*1e9, [-3] = 60*1e9. Gap 540*1e9 ns -> 540s.
        # Duration 60s. 540 > 60*2. True.
        self.assertTrue(is_opening_bar(df, duration))

        # [-2] = 60*1e9, [-3] = 0. Gap 60s. False.
        self.assertFalse(is_opening_bar(df.iloc[:3], duration))

    def test_not_enough_data(self):
        df = pd.DataFrame({"datetime": [1, 2], "close": [1, 1]})
        self.assertFalse(is_opening_bar(df, 5))


if __name__ == "__main__":
    unittest.main()
