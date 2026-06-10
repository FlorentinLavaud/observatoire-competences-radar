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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offres (
                id VARCHAR PRIMARY KEY,
                source VARCHAR,
                titre VARCHAR,
                secteur VARCHAR,
                code_naf VARCHAR,
                code_rome VARCHAR,
                rome_libelle VARCHAR,
                appellation_libelle VARCHAR,
                type_contrat VARCHAR,
                type_contrat_libelle VARCHAR,
                nature_contrat VARCHAR,
                experience_exige VARCHAR,
                experience_libelle VARCHAR,
                nom_acheteur VARCHAR,
                code_departement VARCHAR,
                nombre_postes INTEGER,
                accessible_th BOOLEAN,
                offres_manque_candidats BOOLEAN,
                description TEXT,
                date_publication DATE,
                date_creation TIMESTAMP,
                date_modification TIMESTAMP,
                raw_data JSON
            )
        """)
        logger.info("Table 'offres' initialisée")

        # Faire évoluer le schéma si la table existe déjà
        migrations = [
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS source VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS code_rome VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS rome_libelle VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS appellation_libelle VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS type_contrat VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS type_contrat_libelle VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS nature_contrat VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS experience_exige VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS experience_libelle VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS nom_acheteur VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS code_departement VARCHAR",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS nombre_postes INTEGER",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS accessible_th BOOLEAN",
            "ALTER TABLE offres ADD COLUMN IF NOT EXISTS offres_manque_candidats BOOLEAN"
        ]
        for migration in migrations:
            conn.execute(migration)

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
                raw_data = offer.get("raw_data")
                if raw_data is None:
                    raw_data = offer

                conn.execute("""
                    INSERT OR REPLACE INTO offres 
                    (id, source, titre, secteur, code_naf, code_rome, rome_libelle, appellation_libelle,
                     type_contrat, type_contrat_libelle, nature_contrat, experience_exige, experience_libelle,
                     nom_acheteur, code_departement, nombre_postes, accessible_th, offres_manque_candidats,
                     description, date_publication, date_creation, date_modification, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    offer.get("id", ""),
                    offer.get("source", "france_travail"),
                    offer.get("titre", ""),
                    offer.get("secteur", ""),
                    offer.get("code_naf", ""),
                    offer.get("code_rome", ""),
                    offer.get("rome_libelle", ""),
                    offer.get("appellation_libelle", ""),
                    offer.get("type_contrat", ""),
                    offer.get("type_contrat_libelle", ""),
                    offer.get("nature_contrat", ""),
                    offer.get("experience_exige", ""),
                    offer.get("experience_libelle", ""),
                    offer.get("nom_acheteur", ""),
                    offer.get("code_departement", ""),
                    offer.get("nombre_postes"),
                    offer.get("accessible_th", False),
                    offer.get("offres_manque_candidats", False),
                    offer.get("description", ""),
                    offer.get("date_publication"),
                    offer.get("date_creation"),
                    offer.get("date_modification"),
                    json.dumps(raw_data, default=str)
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
