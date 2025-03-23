import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api.routes import journal, memoire, ai, search, admin, export, hallucination  # Inclure le nouveau module hallucination
from core.config import settings
from core.logging import configure_logging
from db.database import initialize_db, initialize_vectordb

# Configuration du logging
configure_logging()
logger = logging.getLogger(__name__)

# Création de l'application FastAPI
app = FastAPI(
    title="API Assistant de Rédaction de Mémoire",
    description="API pour l'assistant de rédaction de mémoire professionnel",
    version="1.0.0",
    openapi_tags=[
        {"name": "Journal", "description": "Opérations sur le journal de bord"},
        {"name": "Mémoire", "description": "Opérations sur les sections du mémoire"},
        {"name": "IA", "description": "Fonctionnalités d'intelligence artificielle"},
        {"name": "Recherche", "description": "Recherche sémantique dans les données"},
        {"name": "Export", "description": "Export de documents"},
        {"name": "Admin", "description": "Fonctionnalités d'administration"},
        {"name": "Hallucination", "description": "Détection et correction d'hallucinations"}  # Nouvelle section
    ]
)

# Configuration CORS sécurisée
def configure_cors(app: FastAPI):
    """Configure les CORS de manière sécurisée pour l'application"""
    origins = [
        "http://localhost:8501",  # Frontend Streamlit local
        "http://frontend:8501",   # Frontend dans Docker
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )

configure_cors(app)

# Initialisation de la base de données et de l'index vectoriel
try:
    if not initialize_db():
        logger.critical("Échec de l'initialisation de la base de données, mais l'application va tenter de démarrer quand même.")
except Exception as e:
    logger.critical(f"Exception non gérée lors de l'initialisation de la base de données: {str(e)}")

try:
    initialize_vectordb()
except Exception as e:
    logger.critical(f"Exception non gérée lors de l'initialisation de ChromaDB: {str(e)}")

# Inclusion des routeurs
app.include_router(journal, prefix="/journal", tags=["Journal"])
app.include_router(memoire, prefix="/memoire", tags=["Mémoire"])
app.include_router(ai, prefix="/ai", tags=["IA"])
app.include_router(search, prefix="/search", tags=["Recherche"])
app.include_router(export, prefix="/export", tags=["Export"])
app.include_router(admin, prefix="/admin", tags=["Admin"])
app.include_router(hallucination, prefix="/ai", tags=["Hallucination"])

@app.get("/", tags=["Général"])
async def root():
    """Endpoint racine retournant un message d'accueil"""
    return {"message": "Bienvenue sur l'API de l'assistant de rédaction de mémoire professionnel"}

@app.get("/health", tags=["Général"])
async def health_check():
    """Endpoint de vérification de santé pour les health checks"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)