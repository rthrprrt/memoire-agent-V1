"""
Configuration centralisée pour les logs avec rich et loguru dans le frontend Streamlit.
Fournit une présentation améliorée des logs et une gestion unifiée.
"""

import os
import sys
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Rich pour de beaux logs dans la console
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install as install_rich_traceback
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Loguru pour une gestion avancée des logs
try:
    from loguru import logger as loguru_logger
    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False

# Configuration des chemins de logs
LOGS_DIR = Path(__file__).parent.parent / "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Format de date pour les fichiers de logs
DATETIME_FORMAT = "%Y%m%d_%H%M%S"
LOG_FILENAME = f"frontend_{datetime.now().strftime(DATETIME_FORMAT)}.log"

# Format pour les logs
CONSOLE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"

# Niveaux de log
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

def setup_rich_logging():
    """Configure les logs avec Rich pour une sortie console améliorée"""
    if not RICH_AVAILABLE:
        print("Package 'rich' non disponible. Installation recommandée : pip install rich")
        return False
    
    # Installer Rich pour les tracebacks
    install_rich_traceback(show_locals=True)
    
    # Configurer le handler Rich
    console = Console(width=120)
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_extra_lines=2,
        markup=True,
        show_time=True,
        show_path=True
    )
    
    rich_handler.setLevel(LOG_LEVEL)
    rich_handler.setFormatter(logging.Formatter("%(message)s"))
    
    return rich_handler

def setup_file_handler(log_file: Optional[str] = None):
    """Configure un handler pour écrire les logs dans un fichier"""
    if not log_file:
        log_file = LOGS_DIR / LOG_FILENAME
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    
    return file_handler

def configure_logging():
    """Configure le système de logging global"""
    # Réinitialiser les handlers existants
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configurer le niveau de log global
    root_logger.setLevel(LOG_LEVEL)
    
    # Ajouter un handler pour la console
    if RICH_AVAILABLE:
        console_handler = setup_rich_logging()
        root_logger.addHandler(console_handler)
    else:
        # Fallback sur le handler console standard
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVEL)
        console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
        root_logger.addHandler(console_handler)
    
    # Ajouter un handler pour fichier
    file_handler = setup_file_handler()
    root_logger.addHandler(file_handler)
    
    # Configurer Loguru si disponible
    if LOGURU_AVAILABLE:
        configure_loguru()
    
    logging.info(f"Logging configuré avec niveau {LOG_LEVEL}, fichier de logs: {LOGS_DIR / LOG_FILENAME}")
    return root_logger

def configure_loguru():
    """Configure Loguru pour une gestion avancée des logs"""
    if not LOGURU_AVAILABLE:
        return
    
    # Supprimer le handler par défaut
    loguru_logger.remove()
    
    # Ajouter un handler pour la console
    if RICH_AVAILABLE:
        # Utiliser Rich pour la sortie console
        console = Console()
        
        def rich_sink(message):
            record = message.record
            level_name = record["level"].name
            console.print(
                f"[bold][{record['time'].strftime('%H:%M:%S')}]",
                f"[{level_name}]",
                f"[{record['name']}]",
                message
            )
        
        loguru_logger.configure(
            handlers=[
                {"sink": rich_sink, "level": LOG_LEVEL},
                {"sink": str(LOGS_DIR / LOG_FILENAME), "level": LOG_LEVEL}
            ]
        )
    else:
        # Handlers standard sans Rich
        loguru_logger.configure(
            handlers=[
                {"sink": sys.stderr, "level": LOG_LEVEL},
                {"sink": str(LOGS_DIR / LOG_FILENAME), "level": LOG_LEVEL}
            ]
        )

# Intégration avec Streamlit
def configure_streamlit_logging():
    """Configuration spécifique pour les logs dans Streamlit"""
    # Réduire le niveau de log pour les bibliothèques verbeuses
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    
    # Configuration standard
    return configure_logging()

# Pour utiliser loguru au lieu de logging standard
def get_logger(name: str):
    """Retourne un logger Loguru si disponible, sinon un logger standard"""
    if LOGURU_AVAILABLE:
        return loguru_logger.bind(name=name)
    else:
        return logging.getLogger(name)