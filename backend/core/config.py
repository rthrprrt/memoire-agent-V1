import os
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    """Configuration centralisée de l'application"""
    # Base de données
    DB_PATH: str = os.getenv("DB_PATH", "data")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", os.path.join(DB_PATH, "memoire.db"))
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", os.path.join(DB_PATH, "vectordb"))
    
    # LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral:7b")
    
    # API
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: List[str] = [
        "http://localhost:8501",
        "http://frontend:8501"
    ]
    
    # Sécurité
    API_KEY: Optional[str] = os.getenv("API_KEY")
    
    # Stockage
    EXPORT_PATH: str = os.getenv("EXPORT_PATH", os.path.join(DB_PATH, "exports"))
    TEMP_PATH: str = os.getenv("TEMP_PATH", os.path.join(DB_PATH, "temp"))
    CACHE_PATH: str = os.getenv("CACHE_PATH", os.path.join(DB_PATH, "cache"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", "logs/api.log")
    
    # Fonctionnalités
    ENABLE_WEBSOCKETS: bool = os.getenv("ENABLE_WEBSOCKETS", "true").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()