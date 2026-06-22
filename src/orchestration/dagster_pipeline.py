"""
orchestration/dagster_pipeline.py
Pipeline Dagster — Observatoire Compétences Radar
  • Job 1 : france_travail_pipeline  — offres d'emploi → DuckDB → Parquet
  • Job 2 : job_stat_acces_emploi    — taux d'accès à l'emploi → DuckDB
"""
from __future__ import annotations

import os

from dagster import get_dagster_logger, job, op

from src.ingestion.fetchFT import FranceTravailManufacturingScraper
from src.ingestion.fetchStatAccesEmploi import StatAccesEmploiClient
from src.models import StatAccesEmploi
from src.utils.duckdb_handler import (
    export_to_parquet,
    get_duckdb_connection,
    init_schema,
    save_offers_to_duckdb,
)
from src.utils.logger import logger

# ---------------------------------------------------------------------------
# Référentiels métier
# ---------------------------------------------------------------------------

ROME_INDUSTRIE = [
    "H2101", "H2102", "H2201", "H2202", "H2301", "H2401", "H2402",
    "H2403", "H2404", "H2501", "H2502", "H2503", "H2601", "H2602",
    "H2701", "H2801", "H2901", "H2902", "H2903", "H3101", "H3201",
    "H3302", "H3401", "H3403", "I1101",
]

ALL_DEPARTEMENTS = [str(d).zfill(2) for d in range(1, 96)] + ["971", "972", "973", "974"]

DB_PATH = "data/radar.duckdb"

# ---------------------------------------------------------------------------
# Job 1 — Offres d'emploi
# ---------------------------------------------------------------------------

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
    conn = get_duckdb_connection(DB_PATH)
    init_schema(conn)
    save_offers_to_duckdb(conn=conn, offers=records, batch_size=200)
    export_to_parquet(conn, "offres", "data/offres.parquet")
    logger.info("Données persistées et exportées en Parquet")
    return DB_PATH


@job
def france_travail_pipeline():
    """Pipeline d'ingestion France Travail → DuckDB → dbt."""
    persist_to_duckdb(fetch_manufacturing_offers())


# ---------------------------------------------------------------------------
# Job 2 — Statistiques accès à l'emploi
# ---------------------------------------------------------------------------

@op
def fetch_stat_acces_emploi(context):
    """Collecte les taux d'accès à l'emploi (ROME × département) et les persiste dans DuckDB."""
    log = get_dagster_logger()

    client = StatAccesEmploiClient(
        client_id=os.environ["FT_CLIENT_ID"],
        client_secret=os.environ["FT_CLIENT_SECRET"],
    )

    rows_validated = []
    for raw_row in client.iter_stats_industrie(
        codes_rome=ROME_INDUSTRIE,
        codes_departement=ALL_DEPARTEMENTS,
        duree_acces_emploi=6,
    ):
        try:
            rows_validated.append(StatAccesEmploi(**raw_row).model_dump())
        except Exception as exc:
            log.warning(f"Validation échouée : {exc} | row={raw_row}")

    log.info(f"{len(rows_validated)} lignes validées StatAccesEmploi")

    conn = get_duckdb_connection(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_stat_acces_emploi (
            code_rome            VARCHAR,
            libelle_rome         VARCHAR,
            code_departement     VARCHAR,
            libelle_departement  VARCHAR,
            annee                INTEGER,
            duree_acces_emploi   INTEGER,
            taux_acces_emploi    DOUBLE,
            nb_demandeurs        INTEGER,
            type_sortie          VARCHAR,
            rome_query           VARCHAR,
            dept_query           VARCHAR,
            duree_mois           INTEGER
        )
    """)
    conn.executemany(
        "INSERT OR REPLACE INTO raw_stat_acces_emploi VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [list(r.values()) for r in rows_validated],
    )
    log.info("Insertion DuckDB raw_stat_acces_emploi OK")
    return len(rows_validated)


@job
def job_stat_acces_emploi():
    """Pipeline taux d'accès à l'emploi → DuckDB."""
    fetch_stat_acces_emploi()