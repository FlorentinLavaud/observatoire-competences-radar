import unittest
from unittest.mock import Mock, patch

from src.ingestion.fetchFT import FranceTravailManufacturingScraper


class FranceTravailManufacturingScraperTests(unittest.TestCase):
    def test_authenticate_sets_token_and_headers(self):
        scraper = FranceTravailManufacturingScraper("client-id", "secret")

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"access_token": "abc123"}

        with patch("src.ingestion.fetchFT.requests.post", return_value=mock_response) as mocked_post:
            scraper.authenticate()

        self.assertEqual(scraper.token, "abc123")
        self.assertEqual(scraper.headers["Authorization"], "Bearer abc123")
        mocked_post.assert_called_once()

    def test_fetch_offers_by_sector_returns_results_when_response_is_ok(self):
        scraper = FranceTravailManufacturingScraper("client-id", "secret")
        scraper.token = "abc123"
        scraper.headers = {"Authorization": "Bearer abc123", "Accept": "application/json"}

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"resultats": [{"id": "1"}]}
        mock_response.text = "{}"

        with patch.object(scraper.session, "get", return_value=mock_response) as mocked_get:
            results = scraper.fetch_offers_by_sector("10")

        self.assertEqual(results, [{"id": "1"}])
        mocked_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
