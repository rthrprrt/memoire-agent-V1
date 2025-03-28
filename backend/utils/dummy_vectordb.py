"""
Module de fallback pour ChromaDB quand il n'est pas disponible.
Fournit des implémentations simulées des collections et du client ChromaDB.
"""

import logging

logger = logging.getLogger(__name__)

class DummyCollection:
    """Collection simulée pour ChromaDB quand il n'est pas disponible"""
    def __init__(self, name="dummy"):
        self.name = name
        logger.info(f"Création d'une collection simulée '{name}' (mode fallback)")
    
    def add(self, documents=None, embeddings=None, metadatas=None, ids=None, **kwargs):
        """Simule l'ajout de documents à la collection"""
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération add() simulée.")
        return None
    
    def query(self, query_texts=None, query_embeddings=None, n_results=10, **kwargs):
        """Simule une recherche dans la collection"""
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération query() simulée.")
        # Retourne un résultat vide mais correctement formaté
        return {
            "ids": [[]],
            "distances": [[]], 
            "metadatas": [[]],
            "documents": [[]]
        }
    
    def update(self, ids=None, embeddings=None, metadatas=None, documents=None, **kwargs):
        """Simule la mise à jour de documents dans la collection"""
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération update() simulée.")
        return None
    
    def delete(self, ids=None, **kwargs):
        """Simule la suppression de documents de la collection"""
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération delete() simulée.")
        return None
    
    def get(self, ids=None, **kwargs):
        """Simule la récupération de documents de la collection"""
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération get() simulée.")
        return {"ids": [], "metadatas": [], "documents": []}

class DummyClient:
    """Client simulé pour ChromaDB quand il n'est pas disponible"""
    def __init__(self):
        logger.info("Création d'un client ChromaDB simulé (mode fallback)")
    
    def get_collection(self, name):
        """Simule la récupération d'une collection"""
        logger.info(f"Récupération de la collection simulée '{name}' (mode fallback)")
        return DummyCollection(name)
    
    def create_collection(self, name, **kwargs):
        """Simule la création d'une collection"""
        logger.info(f"Création de la collection simulée '{name}' (mode fallback)")
        return DummyCollection(name)
    
    def get_or_create_collection(self, name, **kwargs):
        """Simule la récupération ou création d'une collection"""
        logger.info(f"Récupération ou création de la collection simulée '{name}' (mode fallback)")
        return DummyCollection(name)

def create_dummy_collections():
    """
    Crée un client et des collections simulées pour le mode fallback
    
    Returns:
        tuple: (client, journal_collection, sections_collection)
    """
    logger.info("Initialisation des collections simulées ChromaDB (mode fallback)")
    client = DummyClient()
    journal_collection = DummyCollection("journal_entries")
    sections_collection = DummyCollection("memoire_sections")
    return client, journal_collection, sections_collection