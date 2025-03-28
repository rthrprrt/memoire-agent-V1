import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime
import json
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from api.routes import journal, memoire, ai, search, admin, export, hallucination  # Inclure le nouveau module hallucination
from core.config import settings
from core.logging import configure_logging
from db.database import initialize_db, initialize_vectordb

# Configuration du logging
try:
    from core.logging_config import configure_logging, get_logger
    logger = get_logger(__name__)
    configure_logging()
except ImportError:
    # Fallback sur l'ancienne configuration
    from core.logging import configure_logging
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Utilisation de l'ancien système de logging (core.logging)")

# Personnalisation de la sérialisation JSON pour les dates
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d")
        return super().default(obj)

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

# Override de la méthode par défaut de sérialisation JSON de FastAPI
@app.middleware("http")
async def customize_json_response(request, call_next):
    response = await call_next(request)
    
    # Ne modifie que les réponses JSON
    if response.headers.get("content-type") == "application/json":
        try:
            body = await response.body()
            text = body.decode()
            # Resérialise avec notre encodeur personnalisé
            data = json.loads(text)
            # Ne le fait que si nécessaire
            if any(isinstance(v, datetime) for v in _find_datetime_values(data)):
                text = json.dumps(data, cls=CustomJSONEncoder)
                response = JSONResponse(
                    content=json.loads(text),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
        except Exception as e:
            logger.error(f"Erreur lors de la personnalisation de la réponse JSON: {str(e)}")
    
    return response

# Fonction helper pour trouver les valeurs datetime dans les structures imbriquées
def _find_datetime_values(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _find_datetime_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _find_datetime_values(item)
    elif isinstance(obj, datetime):
        yield obj

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

# Routes directes (pour la compatibilité avec le frontend)
from fastapi import HTTPException, Depends, UploadFile, File, Form, Query, Path
from typing import Optional, List
from services.memory_manager import MemoryManager, get_memory_manager
from api.routes.journal import (
    import_document, analyze_document, 
    cleanup_all_imports, cleanup_document_import, get_import_sources
)
from api.models.journal import JournalEntryOutput, Entreprise, Tag, JournalEntryCreate, JournalEntryUpdate

# Routes d'import de documents
@app.post("/import/document", tags=["Import"])
async def root_import_document(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour l'import de document, redirige vers la route principale"""
    return await import_document(file, entreprise_id, memory_manager)

@app.post("/import/document/analyze", tags=["Import"])
async def root_analyze_document(
    file: UploadFile = File(...)
):
    """Route racine pour l'analyse de document, redirige vers la route principale"""
    return await analyze_document(file)

# Routes entreprises et tags
@app.get("/entreprises", response_model=List[Entreprise], tags=["Journal"])
async def root_get_entreprises(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour récupérer les entreprises"""
    try:
        entreprises = await memory_manager.get_entreprises()
        # Log de débogage pour voir les formats de date 
        if entreprises and len(entreprises) > 0:
            logger.debug(f"Date format dans la réponse: {entreprises[0].get('date_debut', 'N/A')}")
        return entreprises
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entreprises: {str(e)}")
        # En cas d'erreur, retourner une liste vide plutôt qu'une erreur 500
        logger.warning("Retour d'une liste vide suite à une erreur")
        return []

@app.get("/tags", response_model=List[Tag], tags=["Journal"])
async def root_get_tags(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour récupérer les tags"""
    try:
        return await memory_manager.get_tags()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tags: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes journal entries
@app.get("/journal/entries", response_model=List[JournalEntryOutput], tags=["Journal"])
async def root_get_journal_entries(
    start_date: Optional[str] = Query(None, description="Date de début (format YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin (format YYYY-MM-DD)"),
    entreprise_id: Optional[int] = Query(None, description="ID de l'entreprise"),
    type_entree: Optional[str] = Query(None, description="Type d'entrée (quotidien, projet, formation, réflexion)"),
    tag: Optional[str] = Query(None, description="Tag à filtrer"),
    limit: int = Query(50, description="Nombre maximum d'entrées à retourner"),
    offset: int = Query(0, description="Nombre d'entrées à sauter (pour la pagination)"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour récupérer les entrées du journal"""
    try:
        logger.debug(f"Récupération des entrées du journal avec start_date={start_date}, end_date={end_date}")
        entries = await memory_manager.get_journal_entries(
            start_date=start_date,
            end_date=end_date,
            entreprise_id=entreprise_id,
            type_entree=type_entree,
            tag=tag,
            limit=limit,
            offset=offset
        )
        # Log de débogage pour voir les formats de date
        if entries and len(entries) > 0:
            logger.debug(f"Format de date dans la réponse: {entries[0].get('date', 'N/A')}")
        return entries
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entrées: {str(e)}")
        # En cas d'erreur, retourner une liste vide plutôt qu'une erreur 500
        logger.warning("Retour d'une liste vide suite à une erreur")
        return []

@app.post("/journal/entries", response_model=JournalEntryOutput, tags=["Journal"])
async def root_add_journal_entry(
    entry: JournalEntryCreate,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour ajouter une entrée de journal"""
    try:
        result = await memory_manager.add_journal_entry(entry.dict())
        return result
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/journal/entries/{entry_id}", response_model=JournalEntryOutput, tags=["Journal"])
async def root_get_journal_entry(
    entry_id: int = Path(..., description="ID de l'entrée à récupérer"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour récupérer une entrée spécifique"""
    try:
        entry = await memory_manager.get_journal_entry(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération d'une entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/journal/entries/{entry_id}", response_model=JournalEntryOutput, tags=["Journal"])
async def root_update_journal_entry(
    entry_id: int,
    entry: JournalEntryUpdate,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour mettre à jour une entrée de journal"""
    try:
        result = await memory_manager.update_journal_entry(entry_id, entry.dict(exclude_unset=True))
        if not result:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour d'une entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/journal/entries/{entry_id}", tags=["Journal"])
async def root_delete_journal_entry(
    entry_id: int,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour supprimer une entrée de journal"""
    try:
        success = await memory_manager.delete_journal_entry(entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return {"status": "success", "message": "Entrée supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'une entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Route de recherche
@app.get("/search", tags=["Search"])
async def root_search_entries(
    query: str = Query(..., description="Texte à rechercher"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour la recherche dans le journal"""
    try:
        return await memory_manager.search_journal_entries(query)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Route pour la bibliographie
@app.get("/bibliography", tags=["Bibliography"])
async def root_get_bibliography(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour récupérer les références bibliographiques"""
    try:
        return await memory_manager.get_bibliographie()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des références: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bibliography", tags=["Bibliography"])
async def root_add_bibliography_reference(
    reference_data: dict,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour ajouter une référence bibliographique"""
    try:
        return await memory_manager.add_bibliographie_reference(reference_data)
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une référence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Routes pour la gestion des imports de documents
@app.delete("/import/cleanup", tags=["Import"])
async def root_cleanup_all_imports(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour nettoyer tous les imports de documents"""
    try:
        return await cleanup_all_imports(memory_manager)
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des imports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/import/document/{filename}", tags=["Import"])
async def root_cleanup_document_import(
    filename: str,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour nettoyer un import de document spécifique"""
    try:
        return await cleanup_document_import(filename, memory_manager)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de l'import '{filename}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/import/sources", tags=["Import"])
async def root_get_import_sources(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Route racine pour récupérer les sources d'import"""
    try:
        return await get_import_sources(memory_manager)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sources d'import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", tags=["Général"])
async def root():
    """Endpoint racine retournant un message d'accueil"""
    return {"message": "Bienvenue sur l'API de l'assistant de rédaction de mémoire professionnel"}

@app.get("/health", tags=["Général"])
async def health_check():
    """Endpoint de vérification de santé pour les health checks"""
    return {"status": "healthy"}

def print_routes():
    """Affiche toutes les routes API disponibles de manière formatée dans le terminal"""
    try:
        from rich.console import Console
        from rich.table import Table
        from fastapi.routing import APIRoute
        
        console = Console()
        
        # Création d'un tableau Rich pour un affichage formaté
        table = Table(title="Routes API disponibles")
        table.add_column("Méthode", style="cyan")
        table.add_column("Path", style="green")
        table.add_column("Nom", style="yellow")
        table.add_column("Tags", style="magenta")
        
        # Récupération de toutes les routes
        routes = []
        for route in app.routes:
            if isinstance(route, APIRoute):
                routes.append(route)
        
        # Tri des routes par path pour une meilleure lisibilité
        routes.sort(key=lambda r: r.path)
        
        # Ajout des données au tableau
        for route in routes:
            methods = ', '.join(route.methods)
            path = route.path
            name = route.name
            tags = ', '.join(route.tags) if hasattr(route, 'tags') and route.tags else ""
            
            table.add_row(methods, path, name, tags)
        
        # Affichage du tableau
        console.print("\n")
        console.print("[bold blue]==========================================[/bold blue]")
        console.print("[bold blue]= LISTE DES ROUTES API DE L'APPLICATION =[/bold blue]")
        console.print("[bold blue]==========================================[/bold blue]")
        console.print(table)
        console.print(f"[bold green]Total: {len(routes)} routes disponibles[/bold green]")
        console.print("[bold blue]==========================================[/bold blue]\n")
    except ImportError:
        # Fallback si Rich n'est pas disponible
        logger.info("==== LISTE DES ROUTES API DE L'APPLICATION ====")
        
        # Récupération et tri des routes
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods'):
                routes.append(route)
        routes.sort(key=lambda r: r.path)
        
        # Affichage simple des routes
        for route in routes:
            methods = ', '.join(route.methods)
            path = route.path
            name = route.name if hasattr(route, 'name') else ""
            tags = ', '.join(route.tags) if hasattr(route, 'tags') and route.tags else ""
            
            logger.info(f"{methods:<10} {path:<40} {name:<30} Tags: {tags}")
        
        logger.info(f"Total: {len(routes)} routes disponibles")
        logger.info("================================================")
    except Exception as e:
        logger.error(f"Erreur lors de l'affichage des routes: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import Config
    
    # Configuration d'Uvicorn
    config = Config("main:app", host="0.0.0.0", port=8000, reload=True)
    server = uvicorn.Server(config)
    
    # Afficher toutes les routes disponibles avant de démarrer le serveur
    print_routes()
    
    # Démarrer le serveur
    server.run()