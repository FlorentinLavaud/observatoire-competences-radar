# src/run_ingestion.py
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import logger
from src.ingestion.fetchFT import FranceTravailManufacturingScraper

try:
    from src.utils.supabaseClient import create_client, Client
except ImportError:
    logger.critical("Le package 'supabase' est manquant. Installez-le avec : pip install supabase")
    sys.exit(1)

def main():
    """Point d'entrée principal du pipeline d'ingestion."""
    logger.info("=== [START] Lancement du pipeline d'ingestion France Travail ===")

    # 1. Vérification des credentials requis
    required_env_vars = ["FRANCE_TRAVAIL_CLIENT_ID", "FRANCE_TRAVAIL_SECRET_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.critical(f"Pipeline stoppé. Variables d'environnement manquantes : {missing_vars}")
        sys.exit(1)

    try:
        # 2. Initialisation des composants
        supabase_client = get_supabase_client()
        scraper = FranceTravailManufacturingScraper()

        # 3. Exécution du scraping & validation Pydantic intégrée
        validated_offers = scraper.scrape_all_manufacturing()

        # 4. Persistence des données dans Supabase
        save_to_supabase(
            client=supabase_client,
            table_name="offres",
            records=validated_offers,
            batch_size=200
        )

        logger.info("=== [SUCCESS] Fin d'exécution du pipeline d'ingestion ===")

    except Exception as e:
        logger.critical(f"=== [FAILURE] Le pipeline d'ingestion a planté : {e} ===", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()