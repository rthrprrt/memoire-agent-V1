class MemoryManagerException(Exception):
    """Exception de base pour les erreurs du MemoryManager"""
    pass

class DatabaseError(MemoryManagerException):
    """Exception pour les erreurs de base de données"""
    pass

class VectorDBError(MemoryManagerException):
    """Exception pour les erreurs de base de données vectorielle"""
    pass

class LLMError(MemoryManagerException):
    """Exception pour les erreurs liées aux modèles LLM"""
    pass

class ValidationError(MemoryManagerException):
    """Exception pour les erreurs de validation"""
    pass