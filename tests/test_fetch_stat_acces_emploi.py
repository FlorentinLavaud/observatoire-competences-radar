import unittest
from unittest.mock import Mock

from src.ingestion.fetchStatAccesEmploi import StatAccesEmploiClient


class StatAccesEmploiClientTests(unittest.TestCase):
    def test_get_token_uses_documented_scopes(self):
        client = StatAccesEmploiClient("client-id", "client-secret")
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"access_token": "abc123", "expires_in": 3600}
        client.session.post = Mock(return_value=mock_response)

        token = client._get_token()

        self.assertEqual(token, "abc123")
        _, kwargs = client.session.post.call_args
        self.assertEqual(
            kwargs["data"]["scope"],
            "retouremploi api_stats-perspectives-retour-emploiv1",
        )


if __name__ == "__main__":
    unittest.main()
