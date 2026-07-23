import unittest

from src.ingestion.fetchEmploiIndustrie import LindustrieOffer, LindustrieOfferParser

OFFER_HTML = """
<html>
<body class="paged-single paged-offer">
    <script type="application/ld+json">
    {
        "@type": "JobPosting",
        "title": "Soudeur industriel H/F",
        "description": "Poste de soudeur sur site industriel, atelier chaudronnerie.",
        "employmentType": "CDI",
        "datePosted": "2026-04-01T00:00:00Z",
        "hiringOrganization": {"name": "Metallia Industries"},
        "jobLocation": {
            "address": {
                "addressLocality": "Nantes",
                "postalCode": "44000",
                "addressRegion": "Pays de la Loire"
            }
        },
        "identifier": {"name": "REF-2026-042"}
    }
    </script>

    <h1 class="offer-details__title">Soudeur industriel H/F</h1>

    <div class="offer-details__where">44 - Nantes (44000)
        <span class="company">Metallia Industries</span>
    </div>

    <div class="offer-details__metas">
        <span class="ref">Ref : REF-2026-042</span>
    </div>

    <div class="offer-datas">
        <span class="uimm-icon contrat"></span>
        <div>CDI</div>
    </div>
    <div class="offer-datas">
        <span class="uimm-icon experience"></span>
        <div>2 à 5 ans</div>
    </div>
    <div class="offer-datas">
        <span class="uimm-icon etudes"></span>
        <div>CAP / BEP</div>
    </div>
    <div class="offer-datas">
        <span class="uimm-icon time"></span>
        <div>Temps plein</div>
    </div>

    <div class="offer-card__datas-item">
        <span class="uimm-icon salaire"></span>
        Entre 26 000 € et 30 000 € brut annuel
    </div>
</body>
</html>
"""

NOT_FOUND_HTML = """
<html><body class="error404"><h1>Page introuvable</h1></body></html>
"""

WAF_HTML = """
<html><body><script src="https://xyz.awswaf.net/challenge.js"></script></body></html>
"""

EMPTY_HTML = "<html><head></head></html>"


class LindustrieOfferParserPageTypeTests(unittest.TestCase):
    def test_detects_offer_page(self):
        parser = LindustrieOfferParser(1, OFFER_HTML)
        self.assertEqual(parser.page_type(), "offer")

    def test_detects_404_page(self):
        parser = LindustrieOfferParser(1, NOT_FOUND_HTML)
        self.assertEqual(parser.page_type(), "404")

    def test_detects_waf_page_via_script_src(self):
        parser = LindustrieOfferParser(1, WAF_HTML)
        self.assertEqual(parser.page_type(), "waf")

    def test_detects_waf_when_no_body_tag(self):
        parser = LindustrieOfferParser(1, EMPTY_HTML)
        self.assertEqual(parser.page_type(), "waf")


class LindustrieOfferParserParseTests(unittest.TestCase):
    def test_parse_returns_page_type_marker_for_non_offer_pages(self):
        self.assertEqual(LindustrieOfferParser(1, NOT_FOUND_HTML).parse(), "404")
        self.assertEqual(LindustrieOfferParser(1, WAF_HTML).parse(), "waf")

    def test_parse_extracts_offer_fields_from_json_ld_and_css(self):
        parser = LindustrieOfferParser(999888, OFFER_HTML)

        offer = parser.parse()

        self.assertIsInstance(offer, LindustrieOffer)
        self.assertEqual(offer.id, "999888")
        self.assertEqual(offer.source, "lindustrie_recrute")
        self.assertEqual(offer.titre, "Soudeur industriel H/F")
        self.assertEqual(offer.nom_acheteur, "Metallia Industries")
        self.assertEqual(offer.type_contrat, "CDI")
        self.assertEqual(offer.type_contrat_libelle, "CDI")
        self.assertEqual(offer.nature_contrat, "Temps plein")
        self.assertEqual(offer.experience_libelle, "2 à 5 ans")
        self.assertEqual(offer.qualification_libelle, "CAP / BEP")
        self.assertEqual(offer.code_departement, "44")
        self.assertEqual(offer.date_publication, "2026-04-01")
        self.assertEqual(offer.reference_interne, "REF-2026-042")
        self.assertFalse(offer.alternance)
        self.assertIn("26 000", offer.salaire_libelle)

    def test_parse_falls_back_to_json_ld_location_when_css_selector_absent(self):
        html_without_where_div = OFFER_HTML.replace(
            '<div class="offer-details__where">44 - Nantes (44000)\n'
            '        <span class="company">Metallia Industries</span>\n'
            "    </div>",
            "",
        )
        parser = LindustrieOfferParser(1, html_without_where_div)

        offer = parser.parse()

        self.assertEqual(offer.lieu_travail_libelle, "Nantes (44000)")
        self.assertEqual(offer.code_departement, "44")
        self.assertEqual(offer.region, "Pays de la Loire")
        # sans .offer-details__where, le nom d'entreprise vient du JSON-LD
        self.assertEqual(offer.nom_acheteur, "Metallia Industries")

    def test_parse_marks_alternance_contracts(self):
        html = OFFER_HTML.replace(
            '<div class="uimm-icon contrat"></div>\n        <div>CDI</div>',
            "",
        ).replace(
            '<span class="uimm-icon contrat"></span>\n        <div>CDI</div>',
            '<span class="uimm-icon contrat"></span>\n        <div>Alternance</div>',
        )
        parser = LindustrieOfferParser(1, html)

        offer = parser.parse()

        self.assertTrue(offer.alternance)

    def test_parse_ignores_salaire_selon_profil(self):
        html = OFFER_HTML.replace(
            "Entre 26 000 € et 30 000 € brut annuel", "Selon profil"
        )
        parser = LindustrieOfferParser(1, html)

        offer = parser.parse()

        self.assertIsNone(offer.salaire_libelle)


class LindustrieOfferParserHelperTests(unittest.TestCase):
    def test_clean_collapses_whitespace(self):
        self.assertEqual(LindustrieOfferParser._clean("  a   b\n c  "), "a b c")

    def test_clean_returns_none_for_empty_input(self):
        self.assertIsNone(LindustrieOfferParser._clean(""))
        self.assertIsNone(LindustrieOfferParser._clean(None))
        self.assertIsNone(LindustrieOfferParser._clean("   "))

    def test_parse_lieu_extracts_code_departement_from_5_digit_postal_code(self):
        parser = LindustrieOfferParser(1, OFFER_HTML)
        code_dept, libelle, _region = parser._parse_lieu()

        self.assertEqual(code_dept, "44")
        self.assertIn("Nantes (44000)", libelle)

    def test_parse_reference_extracts_value_after_ref_prefix(self):
        parser = LindustrieOfferParser(1, OFFER_HTML)
        self.assertEqual(parser._parse_reference(), "REF-2026-042")

    def test_parse_reference_returns_none_when_absent(self):
        html = OFFER_HTML.replace('<span class="ref">Ref : REF-2026-042</span>', "")
        parser = LindustrieOfferParser(1, html)
        self.assertIsNone(parser._parse_reference())


if __name__ == "__main__":
    unittest.main()