import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import logger
from src.ingestion.fetchFT import FranceTravailManufacturingScraper
from src.utils.duckdb_handler import get_duckdb_connection, init_schema, save_offers_to_duckdb, export_to_parquet

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(project_root, ".env")
if load_dotenv(dotenv_path):
    logger.info(f"Variables d'environnement chargées depuis {dotenv_path}")
else:
    logger.warning(f"Fichier .env non trouvé dans {project_root}. Chargement des variables d'environnement système uniquement.")

def main():
    """Point d'entrée principal du pipeline d'ingestion France Travail → DuckDB."""
    logger.info("=== [START] Lancement du pipeline d'ingestion France Travail ===")

    required_env_vars = ["FRANCE_TRAVAIL_CLIENT_ID", "FRANCE_TRAVAIL_SECRET_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.critical(f"Pipeline stoppé. Variables d'environnement manquantes : {missing_vars}")
        sys.exit(1)

    try:
        # Initialiser la connexion DuckDB
        db_conn = get_duckdb_connection("data/radar.duckdb")
        init_schema(db_conn)
        
        # Collecter et valider les offres
        scraper = FranceTravailManufacturingScraper()
        validated_offers = scraper.scrape_all_manufacturing()

        # Sauvegarder dans DuckDB
        save_offers_to_duckdb(
            conn=db_conn,
            offers=validated_offers,
            batch_size=200,
        )
        
        # Exporter en Parquet pour dbt
        export_to_parquet(db_conn, "offres", "data/offres.parquet")

        logger.info("=== [SUCCESS] Fin d'exécution du pipeline d'ingestion ===")

    except Exception as e:
        logger.critical(f"=== [FAILURE] Le pipeline d'ingestion a planté : {e} ===", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

