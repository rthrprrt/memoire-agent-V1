import logging
import os
from pathlib import Path
from core.config import settings

def configure_logging():
    """Configure le système de logging pour l'application"""
    # Créer le répertoire des logs s'il n'existe pas
    if settings.LOG_FILE:
        log_dir = os.path.dirname(settings.LOG_FILE)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Configuration du format des logs
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configuration du niveau de log
    log_level = getattr(logging, settings.LOG_LEVEL.upper())
    
    # Configuration des handlers
    handlers = []
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    handlers.append(console_handler)
    
    # Handler pour le fichier de log
    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)
    
    # Configuration globale
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )
    
    # Réduire le niveau de log des bibliothèques trop verbeuses
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    logging.info("Système de logging configuré")