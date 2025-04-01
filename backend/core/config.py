import os
from typing import List, Optional

try:
    # Pydantic v2
    from pydantic_settings import BaseSettings
except ImportError:
    # Fallback pour Pydantic v1
    from pydantic import BaseSettings

class Settings(BaseSettings):
    """Configuration centralisée de l'application"""
    # Base de données
    DB_PATH: str = os.getenv("DB_PATH", "data")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", os.path.join(DB_PATH, "memoire.db"))
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", os.path.join(DB_PATH, "vectordb"))
    # Forcer l'utilisation du mode sans ChromaDB en cas de problème
    USE_DUMMY_VECTORDB: bool = os.getenv("USE_DUMMY_VECTORDB", "true").lower() == "true"
    
    # LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "sk-c6513222ef3649c496863e035c77a3dd")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    USE_DEEPSEEK: bool = os.getenv("USE_DEEPSEEK", "true").lower() == "true"
    DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral:7b")
    USE_DUMMY_LLM: bool = os.getenv("USE_DUMMY_LLM", "false").lower() == "true"
    
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
    
    # Support pour Pydantic v1 et v2
    try:
        # Pydantic v2
        model_config = {
            "env_file": ".env",
            "case_sensitive": True
        }
    except:
        # Pydantic v1 fallback
        class Config:
            env_file = ".env"
            case_sensitive = True

settings = Settings()