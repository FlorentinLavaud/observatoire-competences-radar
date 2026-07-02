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

    def test_iter_stats_industrie_does_not_forward_duration_to_request(self):
        client = StatAccesEmploiClient("client-id", "client-secret")

        def fake_rechercher_stat_acces_emploi(*, code_rome=None, code_departement=None, **kwargs):
            self.assertNotIn("duree_acces_emploi", kwargs)
            return [{"code": "ok"}]

        client.rechercher_stat_acces_emploi = fake_rechercher_stat_acces_emploi

        rows = list(client.iter_stats_industrie(["A1234"], ["01"], duree_acces_emploi=6, sleep_between=0))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["_duree_mois"], 6)

    def test_rechercher_stat_acces_emploi_uses_department_territory_by_default(self):
        client = StatAccesEmploiClient("client-id", "client-secret")
        client._get_token = Mock(return_value="abc123")

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"resultats": []}
        client.session.post = Mock(return_value=mock_response)

        client.rechercher_stat_acces_emploi(code_rome="A1234", code_departement="73")

        _, kwargs = client.session.post.call_args
        self.assertEqual(kwargs["json"]["codeTypeTerritoire"], "DEP")


if __name__ == "__main__":
    unittest.main()
