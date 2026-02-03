import unittest
from unittest.mock import patch
from py_entry.scanner.throttler import TimeWindowThrottler


class TestTimeWindowThrottler(unittest.TestCase):
    def setUp(self):
        # period=300s (5min), window=10s
        self.throttler = TimeWindowThrottler(period_seconds=300, window_seconds=10)

    @patch("time.time")
    def test_in_window_at_start(self, mock_time):
        # t=0 => mod=0, within [0, 10]
        mock_time.return_value = 0
        self.assertTrue(self.throttler.is_in_window())

        mock_time.return_value = 5
        self.assertTrue(self.throttler.is_in_window())

        # 10 is OUTSIDE (offset < window_seconds, i.e., offset < 10)
        # So 9.99 is True, 10 is False
        mock_time.return_value = 9.9
        self.assertTrue(self.throttler.is_in_window())

    @patch("time.time")
    def test_in_window_at_end_of_period(self, mock_time):
        # The window is ONLY at the START of the period.
        # [0, 10) is active. [10, 300) is inactive.
        # So 295 is NOT in window.

        # Wait, let's re-read the implementation.
        # offset = time.time() % period
        # return offset < window

        # So window IS [0, 10).
        # t=295 => offset=295. 295 < 10 is False.
        mock_time.return_value = 295
        self.assertFalse(self.throttler.is_in_window())

        # Next cycle start
        mock_time.return_value = 300  # offset 0
        self.assertTrue(self.throttler.is_in_window())

        mock_time.return_value = 605  # offset 5
        self.assertTrue(self.throttler.is_in_window())

    @patch("time.time")
    def test_outside_window(self, mock_time):
        # t=150 => mod=150, outside [0,10]
        mock_time.return_value = 150
        self.assertFalse(self.throttler.is_in_window())

        mock_time.return_value = 11
        self.assertFalse(self.throttler.is_in_window())
