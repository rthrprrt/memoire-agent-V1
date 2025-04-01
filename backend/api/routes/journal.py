from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from datetime import datetime
import logging

from api.models.journal import JournalEntry, JournalImportResponse
from db.repositories.journal_repository import JournalRepository
from utils.text_analysis import analyze_tag_relationships, TagMatrix

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/journal",
    tags=["journal"],
)

@router.post("/entries", response_model=Dict[str, Any])
async def create_journal_entry(entry: JournalEntry):
    """
    Crée une nouvelle entrée de journal
    """
    try:
        repo = JournalRepository()
        created_entry = repo.create_entry(entry)
        return created_entry
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries", response_model=List[Dict[str, Any]])
async def get_journal_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entreprise_id: Optional[int] = None,
    type_entree: Optional[str] = None,
    tag: Optional[str] = None,
    source_document: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Récupère les entrées du journal avec filtres optionnels
    """
    try:
        repo = JournalRepository()
        entries = repo.get_entries(
            start_date=start_date, 
            end_date=end_date,
            entreprise_id=entreprise_id,
            type_entree=type_entree,
            tag=tag,
            source_document=source_document,
            limit=limit,
            offset=offset
        )
        return entries
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entrées: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries/{entry_id}", response_model=Dict[str, Any])
async def get_journal_entry(entry_id: int):
    """
    Récupère une entrée spécifique du journal
    """
    try:
        repo = JournalRepository()
        entry = repo.get_entry_by_id(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'entrée {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/entries/{entry_id}", response_model=Dict[str, Any])
async def update_journal_entry(entry_id: int, entry: JournalEntry):
    """
    Met à jour une entrée existante du journal
    """
    try:
        repo = JournalRepository()
        updated_entry = repo.update_entry(entry_id, entry)
        if not updated_entry:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return updated_entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de l'entrée {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entries/{entry_id}", response_model=Dict[str, str])
async def delete_journal_entry(entry_id: int):
    """
    Supprime une entrée du journal
    """
    try:
        repo = JournalRepository()
        success = repo.delete_entry(entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return {"status": "success", "message": "Entrée supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'entrée {entry_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/document", response_model=JournalImportResponse)
async def import_document(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
):
    """
    Importe un document (PDF ou DOCX) dans le journal
    """
    try:
        # Cette fonction est implémentée dans main.py
        # Redirection vers /import/document
        from main import import_document as main_import_document
        return await main_import_document(file, entreprise_id)
    except Exception as e:
        logger.error(f"Erreur lors de l'import du document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/document/analyze")
async def analyze_document(
    file: UploadFile = File(...),
):
    """
    Analyse un document sans l'importer dans la base de données
    """
    try:
        # Cette fonction est implémentée dans main.py
        # Redirection vers /import/document/analyze
        from main import analyze_document_without_import
        return await analyze_document_without_import(file)
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse du document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/import/sources")
async def get_import_sources():
    """
    Liste tous les documents sources utilisés pour les imports
    """
    try:
        # Cette fonction est implémentée dans main.py
        # Redirection vers /journal/import/sources
        from main import get_import_sources
        return await get_import_sources()
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sources d'import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/import/cleanup")
async def cleanup_all_imports():
    """
    Supprime toutes les entrées créées à partir de documents importés
    """
    try:
        # Cette fonction est implémentée dans main.py
        # Redirection vers /journal/import/cleanup
        from main import cleanup_all_imports
        return await cleanup_all_imports()
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des imports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/import/document/{filename}")
async def cleanup_document_import(filename: str):
    """
    Supprime les entrées créées à partir d'un document spécifique
    """
    try:
        # Cette fonction est implémentée dans main.py
        # Redirection vers /journal/import/document/{filename}
        from main import cleanup_document_import as main_cleanup_document_import
        return await main_cleanup_document_import(filename)
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de l'import '{filename}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tags/analysis")
async def analyze_journal_tags(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entreprise_id: Optional[int] = None,
    min_tags: int = 3,
    max_themes: int = 5
):
    """
    Analyse les tags et thématiques du journal
    
    Cette fonction permet d'analyser les relations entre les tags des entrées de journal
    et d'identifier les thématiques principales.
    
    Args:
        start_date: Date de début pour le filtrage (format YYYY-MM-DD)
        end_date: Date de fin pour le filtrage (format YYYY-MM-DD)
        entreprise_id: ID de l'entreprise pour le filtrage
        min_tags: Nombre minimum de tags par thématique
        max_themes: Nombre maximum de thématiques à extraire
        
    Returns:
        Dict: Analyse des tags avec thématiques identifiées, statistiques, etc.
    """
    try:
        # Récupérer les entrées avec leurs tags
        repo = JournalRepository()
        entries = repo.get_entries(
            start_date=start_date, 
            end_date=end_date,
            entreprise_id=entreprise_id
        )
        
        # Si pas d'entrées, retourner un résultat vide
        if not entries:
            return {
                "tags": [],
                "themes": [],
                "co_occurrences": [],
                "entry_count": 0,
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
        
        # Analyser les relations entre tags
        tag_matrix = analyze_tag_relationships(entries)
        
        # Extraire les thématiques
        themes = tag_matrix.extract_themes(min_tags=min_tags, max_themes=max_themes)
        
        # Récupérer les tags les plus fréquents
        top_tags = tag_matrix.get_top_tags(limit=30)
        
        # Récupérer les co-occurrences les plus fréquentes
        top_co_occurrences = tag_matrix.get_top_co_occurrences(limit=20)
        co_occurrences = [
            {"tags": [t1, t2], "count": count} 
            for (t1, t2), count in top_co_occurrences
        ]
        
        # Construire et retourner le résultat
        return {
            "tags": [{"tag": tag, "count": count} for tag, count in top_tags],
            "themes": themes,
            "co_occurrences": co_occurrences,
            "entry_count": tag_matrix.entry_count,
            "period": {
                "start_date": start_date or (tag_matrix.first_date.isoformat() if tag_matrix.first_date else None),
                "end_date": end_date or (tag_matrix.last_date.isoformat() if tag_matrix.last_date else None)
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse des tags: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))