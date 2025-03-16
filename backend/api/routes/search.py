from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any
import logging

from services.memory_manager import MemoryManager, get_memory_manager

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[Dict[str, Any]])
async def search_entries(
    query: str = Query(..., description="Texte à rechercher"),
    limit: int = Query(5, description="Nombre maximum de résultats"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Recherche des entrées dans le journal par similarité sémantique
    
    Cette fonction permet de trouver des entrées du journal qui correspondent au texte de recherche.
    """
    try:
        return await memory_manager.search_journal_entries(query, limit)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        return []

@router.get("/sections", response_model=List[Dict[str, Any]])
async def search_sections(
    query: str = Query(..., description="Texte à rechercher"),
    limit: int = Query(5, description="Nombre maximum de résultats"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Recherche des sections du mémoire par similarité sémantique
    
    Cette fonction permet de trouver des sections du mémoire qui correspondent au texte de recherche.
    """
    try:
        return await memory_manager.search_relevant_sections(query, limit)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de sections: {str(e)}")
        return []

@router.get("/unified", response_model=Dict[str, Any])
async def unified_search(
    query: str = Query(..., description="Texte à rechercher"),
    limit: int = Query(5, description="Nombre maximum de résultats par catégorie"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Recherche unifiée dans les entrées du journal et les sections du mémoire
    
    Cette fonction permet de rechercher en parallèle dans les différentes sources de données.
    """
    try:
        # Exécuter les recherches en parallèle
        journal_entries_task = memory_manager.search_journal_entries(query, limit)
        sections_task = memory_manager.search_relevant_sections(query, limit)
        
        # Attendre les résultats
        import asyncio
        journal_entries, sections = await asyncio.gather(journal_entries_task, sections_task)
        
        return {
            "journal_entries": journal_entries,
            "sections": sections,
            "total_results": len(journal_entries) + len(sections)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la recherche unifiée: {str(e)}")
        return {
            "journal_entries": [],
            "sections": [],
            "total_results": 0,
            "error": str(e)
        }