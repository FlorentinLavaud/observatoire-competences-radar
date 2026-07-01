"""
Client API France Travail — Accès à l'emploi des demandeurs d'emploi
Endpoint : GET /partenaire/acces-emploi-demandeurs-emploi/v1/stat
Scope    : api_acces-emploi-demandeurs-emploiv1
"""
from __future__ import annotations

import time
from typing import Iterator

import requests

from src.utils.logger import logger



BASE_URL = "https://api.francetravail.io/partenaire/acces-emploi-demandeurs-emploi/v1"
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SCOPE = "api_acces-emploi-demandeurs-emploiv1"


class StatAccesEmploiClient:
    """Client pour l'API Accès à l'emploi des demandeurs d'emploi."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

        if not self.client_id or not self.client_secret:
            logger.critical("FRANCE_TRAVAIL_CLIENT_ID ou FRANCE_TRAVAIL_SECRET_KEY manquant.")
            raise ValueError("Les identifiants France Travail sont requis pour StatAccesEmploiClient.")

        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------
    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token

        # Generer le token OAuth2 avec client credentials envoyés dans le corps.
        # On utilise le même pattern que le scraper France Travail pour éviter les 400.
        resp = self.session.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": SCOPE,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=30,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            logger.error(
                "Échec OAuth2 StatAccesEmploi (%s) : %s",
                resp.status_code,
                resp.text,
            )
            raise exc
        payload = resp.json()
        self._token = payload["access_token"]

        # Sécurité : si l'API ne renvoie pas d'expires_in, on applique 1499s par défaut
        self._token_expires_at = time.time() + payload.get("expires_in", 1499)
        logger.debug("Token StatAccesEmploi renouvelé.")
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Référentiels (utiles pour construire les requêtes)
    # ------------------------------------------------------------------
    def get_activites(self) -> list[dict]:
        """Retourne les codes ROME disponibles dans l'API."""
        resp = self.session.get(f"{BASE_URL}/activites", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_territoires(self) -> list[dict]:
        """Retourne les territoires (départements) disponibles."""
        resp = self.session.get(f"{BASE_URL}/territoires", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_periodes(self) -> list[dict]:
        """Retourne les périodes disponibles."""
        resp = self.session.get(f"{BASE_URL}/periodes", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Requête principale
    # ------------------------------------------------------------------
    def rechercher_stat_acces_emploi(
        self,
        code_rome: str | None = None,
        code_departement: str | None = None,
        annee: int | None = None,
        duree_acces_emploi: int = 6,   # 6 ou 12 mois
        type_sortie: str | None = None,
    ) -> dict:
        """
        Appelle rechercherStatAccesEmploi.
        Retourne le JSON brut de l'API.
        """
        params: dict = {"dureeAccesEmploi": duree_acces_emploi}
        if code_rome:
            params["codeRome"] = code_rome
        if code_departement:
            params["codeDepartement"] = code_departement
        if annee:
            params["annee"] = annee
        if type_sortie:
            params["typeSortie"] = type_sortie

        resp = self.session.get(
            f"{BASE_URL}/stat",
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Itérateur batch : cross produit ROME × département
    # ------------------------------------------------------------------
    def iter_stats_industrie(
        self,
        codes_rome: list[str],
        codes_departement: list[str],
        duree_acces_emploi: int = 6,
        sleep_between: float = 0.3,
    ) -> Iterator[dict]:
        """
        Itère sur tous les couples (ROME, département) et yield
        chaque résultat enrichi avec les clés de contexte.
        """
        total = len(codes_rome) * len(codes_departement)
        logger.info(
            "Lancement fetch StatAccesEmploi : %d ROME × %d dépts = %d requêtes",
            len(codes_rome), len(codes_departement), total,
        )
        for rome in codes_rome:
            for dept in codes_departement:
                try:
                    data = self.rechercher_stat_acces_emploi(
                        code_rome=rome,
                        code_departement=dept,
                        duree_acces_emploi=duree_acces_emploi,
                    )
                    # Normalise en liste de lignes plates
                    resultats = data if isinstance(data, list) else data.get("resultats", [data])
                    for row in resultats:
                        row.setdefault("_rome_query", rome)
                        row.setdefault("_dept_query", dept)
                        row.setdefault("_duree_mois", duree_acces_emploi)
                        yield row
                except requests.HTTPError as exc:
                    logger.warning("HTTP %s pour ROME=%s DEPT=%s : %s", exc.response.status_code, rome, dept, exc)
                except Exception as exc:
                    logger.error("Erreur inattendue ROME=%s DEPT=%s : %s", rome, dept, exc)
                finally:
                    time.sleep(sleep_between)