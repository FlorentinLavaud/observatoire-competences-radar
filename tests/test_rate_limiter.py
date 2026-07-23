import unittest

from src.ingestion.fetchEmploiIndustrie import GlobalRateLimiter


class GlobalRateLimiterThrottleTests(unittest.TestCase):
    def test_starts_at_nominal_speed(self):
        limiter = GlobalRateLimiter(rate_per_sec=3.0, burst=5)
        self.assertEqual(limiter._slowdown, 1.0)

    def test_throttle_signal_increases_slowdown(self):
        limiter = GlobalRateLimiter(rate_per_sec=3.0, burst=5)

        limiter.report_throttle_signal()

        self.assertGreater(limiter._slowdown, 1.0)

    def test_throttle_signal_is_capped_at_8x(self):
        limiter = GlobalRateLimiter(rate_per_sec=3.0, burst=5)

        for _ in range(20):
            limiter.report_throttle_signal()

        self.assertLessEqual(limiter._slowdown, 8.0)

    def test_ok_signal_gradually_relaxes_slowdown(self):
        limiter = GlobalRateLimiter(rate_per_sec=3.0, burst=5)
        limiter.report_throttle_signal()
        slowdown_after_throttle = limiter._slowdown

        limiter.report_ok_signal()

        self.assertLess(limiter._slowdown, slowdown_after_throttle)

    def test_ok_signal_never_drops_below_nominal_speed(self):
        limiter = GlobalRateLimiter(rate_per_sec=3.0, burst=5)

        for _ in range(50):
            limiter.report_ok_signal()

        self.assertGreaterEqual(limiter._slowdown, 1.0)

    def test_ok_signal_resets_consecutive_throttle_counter(self):
        limiter = GlobalRateLimiter(rate_per_sec=3.0, burst=5)
        limiter.report_throttle_signal()
        limiter.report_throttle_signal()

        limiter.report_ok_signal()

        self.assertEqual(limiter._consecutive_throttle_hits, 0)


if __name__ == "__main__":
    unittest.main()