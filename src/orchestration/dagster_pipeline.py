from dagster import job, op
import duckdb

from src.ingestion.fetchFT import FranceTravailManufacturingScraper
from src.utils.logger import logger
from src.utils.duckdb_handler import (
    get_duckdb_connection,
    init_schema,
    save_offers_to_duckdb,
    export_to_parquet
)


@op
def fetch_manufacturing_offers() -> list[dict]:
    """Collecte les offres industrielles France Travail et les valide via Pydantic."""
    scraper = FranceTravailManufacturingScraper()
    offers = scraper.scrape_all_manufacturing()
    logger.info(f"Offres collectées et validées : {len(offers)}")
    return offers


@op
def persist_to_duckdb(records: list[dict]) -> str:
    """Persiste les offres validées dans DuckDB et exporte en Parquet."""
    db_conn = get_duckdb_connection("data/radar.duckdb")
    init_schema(db_conn)
    
    save_offers_to_duckdb(
        conn=db_conn,
        offers=records,
        batch_size=200
    )
    
    # Exporter en Parquet pour dbt
    export_to_parquet(db_conn, "offres", "data/offres.parquet")
    
    logger.info(f"Données persistées et exportées en Parquet")
    return "data/radar.duckdb"


@job
def france_travail_pipeline():
    """Pipeline d'ingestion France Travail → DuckDB → dbt."""
    persist_to_duckdb(fetch_manufacturing_offers())

