import unittest

from src.ingestion.fetchEmploiIndustrie import LindustrieScraper


class LindustrieScraperWafTests(unittest.TestCase):
    def test_waf_retry_limit_blocks_looping_offers(self):
        scraper = LindustrieScraper(concurrency=1, id_start=1, id_end=1)

        self.assertTrue(scraper._should_retry_waf(42))
        self.assertTrue(scraper._should_retry_waf(42))
        self.assertTrue(scraper._should_retry_waf(42))
        self.assertFalse(scraper._should_retry_waf(42))


if __name__ == "__main__":
    unittest.main()
