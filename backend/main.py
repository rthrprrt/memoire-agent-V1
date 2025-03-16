"""
Application principale de l'Agent Assistant de Mémoire.
Point d'entrée pour l'API FastAPI.
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

# Import des routeurs
from api.routes.journal import router as journal_router
from api.routes.memoire import router as memoire_router
from api.routes.export import router as export_router
from api.routes.hallucination import router as hallucination_router
from api.routes.ai import router as ai_router
from api.routes.admin import router as admin_router
from api.routes.search import router as search_router

# Import des services et initialisations
from db.initializer import init_db, init_chromadb
from core.memory_manager import init_memory_manager
from core.memory_manager import get_memory_manager
from services.llm_service import initialize_llm

# Configuration du logger
from core.logging import setup_logging
logger = setup_logging()

# Création de l'application FastAPI
app = FastAPI(
    title="API Assistant de Rédaction de Mémoire",
    description="API pour l'assistant de rédaction de mémoire professionnel",
    version="1.0.0"
)

# Configuration CORS
def configure_cors(app: FastAPI):
    origins = [
        "http://localhost:8501",  # Frontend Streamlit local
        "http://frontend:8501",   # Frontend dans Docker
        "*",                      # Temporairement permettre tous les origines pour le développement
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=3600,
    )

configure_cors(app)

# Inclusion des routeurs avec préfixes
app.include_router(journal_router, prefix="/journal", tags=["Journal"])
app.include_router(memoire_router, prefix="/memoire", tags=["Mémoire"])
app.include_router(export_router, prefix="/export", tags=["Export"])
app.include_router(ai_router, prefix="/ai", tags=["Intelligence Artificielle"])
app.include_router(admin_router, prefix="/admin", tags=["Administration"])
app.include_router(hallucination_router, prefix="/verify", tags=["Vérification"])
app.include_router(search_router, prefix="/search", tags=["Recherche"])

# Personnalisation de la documentation OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Assistant Mémoire API",
        version="1.0.0",
        description="API pour l'assistant de rédaction de mémoire professionnel",
        routes=app.routes,
    )
    
    # Personnalisation des tags
    openapi_schema["tags"] = [
        {"name": "Journal", "description": "Opérations sur le journal de bord"},
        {"name": "Mémoire", "description": "Opérations sur les sections du mémoire"},
        {"name": "Export", "description": "Fonctionnalités d'export (PDF, DOCX)"},
        {"name": "Intelligence Artificielle", "description": "Génération et amélioration de contenu"},
        {"name": "Vérification", "description": "Vérification et correction d'hallucinations"},
        {"name": "Administration", "description": "Fonctionnalités d'administration du système"},
        {"name": "Recherche", "description": "Recherche sémantique dans le contenu"}
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Route racine
@app.get("/")
async def root():
    return {
        "message": "Bienvenue sur l'API de l'assistant de rédaction de mémoire professionnel",
        "documentation": "/docs",
        "status": "active"
    }

# Route de santé
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Événements de démarrage et d'arrêt
@app.on_event("startup")
async def startup_event():
    logger.info("Démarrage de l'application...")
    
    # Initialisation de la base de données
    try:
        db_success = init_db()
        if db_success:
            logger.info("Base de données initialisée avec succès")
        else:
            logger.warning("Échec de l'initialisation de la base de données")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
    
    # Initialisation de ChromaDB
    try:
        chromadb_client, journal_collection, sections_collection = init_chromadb()
        logger.info("ChromaDB initialisé avec succès")
    except Exception as e:
        logger.error(f"Échec de l'initialisation de ChromaDB: {str(e)}")
    
    # Initialisation du MemoryManager et enregistrement de l'instance globale
    try:
        from services.memory_service import MemoryManager
        memory_manager = MemoryManager()
        init_memory_manager(memory_manager)
        logger.info("MemoryManager initialisé et enregistré globalement")
    except Exception as e:
        logger.error(f"Échec de l'initialisation du MemoryManager: {str(e)}")
    
    # Initialisation du service LLM
    try:
        llm_service = initialize_llm()
        logger.info("Service LLM initialisé avec succès")
    except Exception as e:
        logger.error(f"Échec de l'initialisation du service LLM: {str(e)}")
    
    logger.info("Application démarrée avec succès")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Arrêt de l'application...")
    # Nettoyage des ressources
    logger.info("Application arrêtée avec succès")

# Point d'entrée pour exécuter l'application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)