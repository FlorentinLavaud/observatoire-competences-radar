# src/utils/logger.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from tqdm import tqdm

class TqdmLoggingHandler(logging.Handler):
    """Handler personnalisé pour écrire les logs sans casser les barres de progression tqdm."""
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(log_level: int = logging.INFO) -> logging.Logger:
    """Configure et retourne le logger global du projet."""
    logger = logging.getLogger("radar_logger")
    
    # Évite d'ajouter des handlers multiples si la fonction est appelée plusieurs fois
    if logger.hasHandlers():
        return logger

    logger.setLevel(log_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Handler Console (Compatible Tqdm)
    console_handler = TqdmLoggingHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Handler Fichier avec Rotation (Sauvegarde locale automatique)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, "scraper.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Initialisation immédiate du logger au chargement du module
logger = setup_logger()