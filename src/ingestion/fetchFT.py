# src/ingestion/france_travail_scrapper.py
import os
import time
import requests
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from src.utils.logger import logger
from src.models import FranceTravailOfferParser


class FranceTravailManufacturingScraper:
    """
    Scraper orienté POO pour l'Industrie Manufacturière (Section C de l'INSEE).
    Utilise le paramètre de la doc 'secteurActivite' (divisions 10 à 33).
    """

    AUTH_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

    def __init__(self, client_id: Optional[str] = None, secret_key: Optional[str] = None):
        self.client_id = client_id or os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
        self.secret_key = secret_key or os.getenv("FRANCE_TRAVAIL_SECRET_KEY")
        self.token: Optional[str] = None
        self.headers: Dict[str, str] = {}

        if not self.client_id or not self.secret_key:
            logger.critical("Impossible d'initialiser le scraper : identifiants manquants.")
            raise ValueError("Les credentials France Travail sont requis.")
        
        logger.debug("FranceTravailManufacturingScraper configuré.")

    def authenticate(self) -> None:
        """Exécute l'authentification OAuth2 (OAuth Client Credentials)."""
        scope = 'api_offresdemploiv2 o2dsoffre'
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.secret_key,
            'scope': scope
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        logger.info("Tentative de récupération du token d'accès...")
        try:
            response = requests.post(self.AUTH_URL, headers=headers, data=payload)
            response.raise_for_status()
            self.token = response.json().get('access_token')
            
            self.headers = {
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/json'
            }
            logger.info("Authentification France Travail validée.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur d'authentification : {e}", exc_info=True)
            raise e

    @staticmethod
    def generate_manufacturing_sectors() -> List[str]:
        """Génère les divisions de l'industrie manufacturière (10 à 33)."""
        return [str(i) for i in range(10, 34)]

    def fetch_offers_by_sector(self, sector_code: str) -> List[Dict[str, Any]]:
        """
        Récupère les offres d'un secteur d'activité (division NAF) spécifique.
        Gère la pagination d'après le système de plages (Content-Range / range) de la doc.
        """
        if not self.token:
            self.authenticate()

        results: List[Dict[str, Any]] = []
        start_index = 0
        step = 149  # La doc stipule : "La plage de résultats est limitée à 150" (ex: 0-149)
        max_bound = 3000 # Contrainte doc : premier index max à 3000

        while start_index <= max_bound:
            end_index = start_index + step
            querystring = {
                "secteurActivite": sector_code,
                "range": f"{start_index}-{end_index}"
            }

            try:
                logger.debug(f"Secteur {sector_code} : Requête sur la plage {start_index}-{end_index}")
                response = requests.get(self.SEARCH_URL, headers=self.headers, params=querystring)
                
                if response.status_code == 204:
                    logger.debug(f"Fin ou absence de données (204) pour le secteur {sector_code}.")
                    break

                # 200 = Tout est récupéré, 206 = Contenu partiel (il reste des pages)
                if response.status_code in [200, 206]:
                    data = response.json()
                    page_results = data.get("resultats", [])
                    results.extend(page_results)
                    
                    if response.status_code == 200 or len(page_results) < 150:
                        # Si l'API renvoie un code 200 ou moins de 150 lignes, on a atteint la fin
                        break
                        
                    start_index += 150
                    time.sleep(0.15) # Quota protection (10 req/sec max)
                else:
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur lors du requêtage du secteur {sector_code} à l'index {start_index}: {e}")
                break

        return results

    def scrape_all_manufacturing(self) -> List[Dict[str, Any]]:
        """Orchestre la collecte globale et retourne les payloads validés prêtes pour la DB."""
        raw_offers: List[Dict[str, Any]] = []
        sectors = self.generate_manufacturing_sectors()
        
        logger.info(f"Lancement du scraping sur {len(sectors)} divisions industrielles.")
        
        for sector in tqdm(sectors, desc="Secteurs Industriels"):
            sector_offers = self.fetch_offers_by_sector(sector)
            raw_offers.extend(sector_offers)
            time.sleep(0.2)

        logger.info(f"Scraping achevé. {len(raw_offers)} offres brutes collectées.")
        
        # Phase de validation sémantique et de nettoyage via Pydantic
        validated_payloads: List[Dict[str, Any]] = []
        for raw_item in raw_offers:
            try:
                # Validation structurelle automatique
                parsed_offer = FranceTravailOfferParser(**raw_item)
                # Transformation en dictionnaire plat conforme au schéma Supabase
                validated_payloads.append(parsed_offer.to_supabase_dict(raw_item))
            except Exception as e:
                logger.warning(f"Offre {raw_item.get('id', 'INCONNUE')} rejetée par validation Pydantic : {e}")
                continue

        logger.info(f"Validation terminée. {len(validated_payloads)} / {len(raw_offers)} offres prêtes pour l'insertion DB.")
        return validated_payloads