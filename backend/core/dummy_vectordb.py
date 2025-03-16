import logging

logger = logging.getLogger(__name__)

class DummyCollection:
    """Collection simulée pour ChromaDB quand il n'est pas disponible"""
    def __init__(self, name="dummy"):
        self.name = name
    
    def add(self, *args, **kwargs):
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération add() simulée.")
        return None
    
    def query(self, *args, **kwargs):
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération query() simulée.")
        return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}
    
    def update(self, *args, **kwargs):
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération update() simulée.")
        return None
    
    def delete(self, *args, **kwargs):
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération delete() simulée.")
        return None
    
    def get(self, *args, **kwargs):
        logger.warning(f"Collection {self.name}: ChromaDB n'est pas disponible. Opération get() simulée.")
        return {"ids": [], "metadatas": [], "documents": []}

class DummyClient:
    """Client simulé pour ChromaDB quand il n'est pas disponible"""
    def get_collection(self, name):
        return DummyCollection(name)
    
    def create_collection(self, name):
        return DummyCollection(name)
    
    def get_or_create_collection(self, name):
        return DummyCollection(name)

def create_dummy_collections():
    """Crée un client et des collections simulées"""
    client = DummyClient()
    journal_collection = DummyCollection("journal_entries")
    sections_collection = DummyCollection("memoire_sections")
    return client, journal_collection, sections_collection