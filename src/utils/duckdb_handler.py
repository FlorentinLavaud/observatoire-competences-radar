"""Gestionnaire DuckDB pour la persistence des données."""
import duckdb
import json
import os
from pathlib import Path
from src.utils.logger import logger


def get_duckdb_connection(db_path: str = "data/radar.duckdb"):
    """Obtient ou crée une connexion DuckDB.
    
    Args:
        db_path: Chemin vers le fichier DuckDB
        
    Returns:
        Connexion DuckDB
    """
    # Créer le répertoire s'il n'existe pas
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = duckdb.connect(db_path)
    logger.info(f"Connexion DuckDB établie: {db_path}")
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection):
    """Initialise le schéma des tables principales."""
    try:
        # Table des offres d'emploi brutes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offres (
                id VARCHAR PRIMARY KEY,
                titre VARCHAR,
                secteur VARCHAR,
                code_naf VARCHAR,
                description TEXT,
                date_publication DATE,
                date_creation TIMESTAMP,
                date_modification TIMESTAMP,
                raw_data JSON
            )
        """)
        logger.info("Table 'offres' initialisée")
        
        # Créer un index sur le secteur et la date pour les performances
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_offres_secteur ON offres(secteur)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_offres_date ON offres(date_publication)
        """)
        logger.info("Index créés")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du schéma: {e}")
        raise


def save_offers_to_duckdb(conn: duckdb.DuckDBPyConnection, offers: list[dict], batch_size: int = 200):
    """Sauvegarde les offres dans DuckDB.
    
    Args:
        conn: Connexion DuckDB
        offers: Liste des offres à sauvegarder
        batch_size: Taille des lots d'insertion
    """
    if not offers:
        logger.warning("Aucune offre à sauvegarder")
        return
    
    try:
        # Insérer par lots
        for i in range(0, len(offers), batch_size):
            batch = offers[i:i + batch_size]
            
            # Préparer les données pour l'insertion
            for offer in batch:
                conn.execute("""
                    INSERT OR REPLACE INTO offres 
                    (id, titre, secteur, code_naf, description, date_publication, date_creation, date_modification, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    offer.get("id", ""),
                    offer.get("titre", ""),
                    offer.get("secteur", ""),
                    offer.get("code_naf", ""),
                    offer.get("description", ""),
                    offer.get("date_publication"),
                    offer.get("date_creation"),
                    offer.get("date_modification"),
                    json.dumps(offer, default=str)
                ])
            
            logger.info(f"Lot {i // batch_size + 1} sauvegardé ({len(batch)} offres)")
        
        conn.commit()
        logger.info(f"Total {len(offers)} offres sauvegardées dans DuckDB")
        
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {e}")
        raise


def export_to_parquet(conn: duckdb.DuckDBPyConnection, table: str, output_path: str):
    """Exporte une table DuckDB en Parquet."""
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        conn.execute(f"COPY {table} TO '{output_path}' (FORMAT PARQUET)")
        logger.info(f"Table '{table}' exportée vers {output_path}")
    except Exception as e:
        logger.error(f"Erreur lors de l'export Parquet: {e}")
        raise
