"""
Module pour la gestion centralisée de l'accès au MemoryManager
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Variable globale pour stocker l'instance unique de MemoryManager
_memory_manager_instance = None

def init_memory_manager(manager_instance):
    """
    Initialiser l'instance globale du MemoryManager.
    
    Args:
        manager_instance: Instance du MemoryManager à utiliser
    """
    global _memory_manager_instance
    _memory_manager_instance = manager_instance
    logger.info("Memory Manager global initialisé")

def get_memory_manager():
    """
    Récupérer l'instance globale du MemoryManager.
    
    Returns:
        L'instance du MemoryManager
    
    Raises:
        RuntimeError: Si le MemoryManager n'a pas été initialisé
    """
    if _memory_manager_instance is None:
        raise RuntimeError("Memory Manager non initialisé. Appelez init_memory_manager d'abord.")
    return _memory_manager_instance

def reset_memory_manager():
    """
    Réinitialiser l'instance globale du MemoryManager.
    Utile pour les tests ou la réinitialisation de l'application.
    """
    global _memory_manager_instance
    _memory_manager_instance = None
    logger.info("Memory Manager réinitialisé")