import unittest

from src.models import FranceTravailOfferParser, StatAccesEmploi


def _make_offer(**overrides):
    """Construit une charge utile France Travail minimale, avec surcharges."""
    payload = {
        "id": "123ABC",
        "intitule": "Technicien de maintenance industrielle",
        "romeCode": "H2101",
        "romeLibelle": "Conduite d'équipement de production",
        "codeNAF": "2511Z",
        "secteurActiviteLibelle": "Fabrication de structures métalliques",
        "typeContrat": "CDI",
        "typeContratLibelle": "Contrat à durée indéterminée",
        "dateCreation": "2026-05-10T08:00:00.000Z",
        "dateActualisation": "2026-05-12T10:30:00Z",
        "lieuTravail": {"libelle": "44 - Nantes"},
        "entreprise": {"nom": "Atelier Dupont"},
        "nombrePostes": 2,
    }
    payload.update(overrides)
    return payload


class FranceTravailOfferParserTests(unittest.TestCase):
    def test_parses_aliases_correctly(self):
        offer = FranceTravailOfferParser(**_make_offer())

        self.assertEqual(offer.titre, "Technicien de maintenance industrielle")
        self.assertEqual(offer.code_rome, "H2101")
        self.assertEqual(offer.code_naf, "2511Z")
        self.assertEqual(offer.type_contrat, "CDI")

    def test_code_departement_extracted_from_lieu_travail_libelle(self):
        offer = FranceTravailOfferParser(**_make_offer())

        self.assertEqual(offer.code_departement, "44")

    def test_code_departement_is_none_without_separator(self):
        offer = FranceTravailOfferParser(**_make_offer(lieuTravail={"libelle": "Nantes"}))

        self.assertIsNone(offer.code_departement)

    def test_code_departement_is_none_without_lieu_travail(self):
        offer = FranceTravailOfferParser(**_make_offer(lieuTravail=None))

        self.assertIsNone(offer.code_departement)

    def test_nom_entreprise_extracted_from_entreprise_dict(self):
        offer = FranceTravailOfferParser(**_make_offer())

        self.assertEqual(offer.nom_entreprise, "Atelier Dupont")

    def test_nom_entreprise_is_none_when_entreprise_missing(self):
        offer = FranceTravailOfferParser(**_make_offer(entreprise=None))

        self.assertIsNone(offer.nom_entreprise)

    def test_secteur_prefers_libelle_then_activite_then_naf(self):
        offer_with_libelle = FranceTravailOfferParser(**_make_offer())
        self.assertEqual(offer_with_libelle.secteur, "Fabrication de structures métalliques")

        offer_with_activite = FranceTravailOfferParser(
            **_make_offer(secteurActiviteLibelle=None, secteurActivite="C25")
        )
        self.assertEqual(offer_with_activite.secteur, "C25")

        offer_with_naf_only = FranceTravailOfferParser(
            **_make_offer(secteurActiviteLibelle=None, secteurActivite=None)
        )
        self.assertEqual(offer_with_naf_only.secteur, "2511Z")

    def test_parse_datetime_handles_both_known_formats(self):
        self.assertIsNotNone(
            FranceTravailOfferParser.parse_datetime("2026-05-10T08:00:00Z")
        )
        self.assertIsNotNone(
            FranceTravailOfferParser.parse_datetime("2026-05-10T08:00:00.123Z")
        )

    def test_parse_datetime_returns_none_for_empty_value(self):
        self.assertIsNone(FranceTravailOfferParser.parse_datetime(None))
        self.assertIsNone(FranceTravailOfferParser.parse_datetime(""))

    def test_parse_datetime_returns_none_for_unparsable_value(self):
        self.assertIsNone(FranceTravailOfferParser.parse_datetime("pas une date"))

    def test_to_dict_uses_creation_date_as_publication_date(self):
        offer = FranceTravailOfferParser(**_make_offer())

        flat = offer.to_dict(raw_entry={"id": "123ABC"})

        self.assertEqual(flat["date_publication"], "2026-05-10")
        self.assertEqual(flat["source"], "france_travail")
        self.assertEqual(flat["code_departement"], "44")
        self.assertEqual(flat["raw_data"], {"id": "123ABC"})

    def test_to_dict_falls_back_to_creation_date_when_actualisation_missing(self):
        offer = FranceTravailOfferParser(**_make_offer(dateActualisation=None))

        flat = offer.to_dict(raw_entry={})

        self.assertEqual(flat["date_modification"], flat["date_creation"])

    def test_to_dict_handles_missing_dates_gracefully(self):
        offer = FranceTravailOfferParser(**_make_offer(dateCreation=None, dateActualisation=None))

        flat = offer.to_dict(raw_entry={})

        self.assertIsNone(flat["date_publication"])
        self.assertIsNone(flat["date_creation"])
        self.assertIsNone(flat["date_modification"])


class StatAccesEmploiTests(unittest.TestCase):
    def test_parses_official_field_aliases(self):
        stat = StatAccesEmploi(
            codeRome="H2101",
            libelleRome="Conduite d'équipement de production",
            codeDepartement="44",
            annee=2025,
            dureeAccesEmploi=6,
            tauxAccesEmploi=42.5,
            nbDemandeurs=1200,
        )

        self.assertEqual(stat.code_rome, "H2101")
        self.assertEqual(stat.code_departement, "44")
        self.assertEqual(stat.taux_acces_emploi, 42.5)

    def test_accepts_internal_fields_by_name(self):
        # Ces champs sont injectés par le client (préfixe "_"), pas par l'API.
        stat = StatAccesEmploi(_rome_query="H2101", _dept_query="44", _duree_mois=6)

        self.assertEqual(stat.rome_query, "H2101")
        self.assertEqual(stat.dept_query, "44")
        self.assertEqual(stat.duree_mois, 6)

    def test_all_fields_optional(self):
        stat = StatAccesEmploi()

        self.assertIsNone(stat.code_rome)
        self.assertIsNone(stat.taux_acces_emploi)


if __name__ == "__main__":
    unittest.main()