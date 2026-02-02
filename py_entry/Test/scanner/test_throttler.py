import unittest
from py_entry.scanner.throttler import TimeWindowThrottler


class TestTimeWindowThrottler(unittest.TestCase):
    def setUp(self):
        # period=300s (5min), window=10s
        self.throttler = TimeWindowThrottler(period_seconds=300, window_seconds=10)

    def test_in_window_at_start(self):
        # t=0 => mod=0, within [0, 10]
        self.assertTrue(self.throttler._is_in_window(0))
        self.assertTrue(self.throttler._is_in_window(5))
        self.assertTrue(self.throttler._is_in_window(10))

    def test_in_window_at_end(self):
        # t=295 => mod=295, within [290, 300)
        self.assertTrue(self.throttler._is_in_window(295))
        self.assertTrue(self.throttler._is_in_window(299))
        self.assertTrue(self.throttler._is_in_window(300))  # mod 0
        self.assertTrue(self.throttler._is_in_window(600))  # mod 0

    def test_outside_window(self):
        # t=150 => mod=150, outside [0,10] and [290,300]
        self.assertFalse(self.throttler._is_in_window(150))
        self.assertFalse(self.throttler._is_in_window(11))
        self.assertFalse(self.throttler._is_in_window(289))
