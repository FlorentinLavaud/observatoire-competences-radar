# src/database.py
import os
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from src.utils.logger import logger

# Variable globale pour stocker l'instance unique du client (Pattern Singleton)
_supabase_instance: Optional[Client] = None

def get_supabase_client() -> Client:
    """Initialise et retourne le client Supabase à partir des variables d'environnement."""
    global _supabase_instance
    
    # Si le client a déjà été initialisé, on retourne l'instance existante
    if _supabase_instance is not None:
        return _supabase_instance

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        logger.critical("Variables d'environnement 'SUPABASE_URL' ou 'SUPABASE_KEY' manquantes.")
        raise ValueError("Supabase non configuré.")
        
    try:
        logger.info("Initialisation du client Supabase...")
        _supabase_instance = create_client(url, key)
        logger.info("Client Supabase initialisé avec succès.")
        return _supabase_instance
    except Exception as e:
        logger.critical(f"Échec de la connexion à Supabase : {e}", exc_info=True)
        raise e


def save_to_supabase(client: Client, table_name: str, records: List[Dict[str, Any]], batch_size: int = 200) -> None:
    """
    Insère ou met à jour (upsert) les enregistrements dans Supabase par lots (batchs)
    pour éviter de surcharger les requêtes HTTP.
    """
    if not records:
        logger.info("Aucun enregistrement à insérer dans la base de données.")
        return

    logger.info(f"Début de l'insertion dans Supabase (Table: {table_name}) de {len(records)} lignes...")
    
    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            # On utilise .upsert() pour éviter les conflits si l'ID de l'offre existe déjà
            response = client.table(table_name).upsert(batch).execute()
            
            # Vérification basique du succès de la réponse
            if response.data:
                total_inserted += len(response.data)
                logger.debug(f"Batch {i // batch_size + 1} inséré avec succès ({len(response.data)} lignes).")
            else:
                logger.warning(f"Le batch {i // batch_size + 1} a renvoyé une réponse vide.")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'insertion du batch {i // batch_size + 1} : {e}", exc_info=True)
            continue

    logger.info(f"Finition de l'écriture en DB. {total_inserted} offres synchronisées avec succès.")