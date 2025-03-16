"""
Routeur FastAPI pour les opérations sur le mémoire.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query, Path
from typing import Dict, Any, Optional, List
import logging

from pydantic import BaseModel, constr, Field, validator
import re

from core.memory_manager import get_memory_manager

# Configuration du logger
logger = logging.getLogger(__name__)

# Création du routeur
router = APIRouter()

# Modèles de données
class MemoireSection(BaseModel):
    """Modèle pour les sections du mémoire."""
    titre: constr(min_length=3, max_length=200)
    content: Optional[constr(max_length=50000)] = None
    ordre: int = Field(..., ge=0, lt=1000)
    parent_id: Optional[int] = None

    class Config:
        extra = "forbid"

    @validator('content')
    def content_must_be_safe(cls, v):
        """Vérifie que le contenu ne contient pas de code malveillant"""
        if v and re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

# Routes API
@router.post("/sections", response_model=Dict[str, Any])
async def add_section(
    section: MemoireSection = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Ajoute une nouvelle section au mémoire.
    """
    try:
        result = await memory_manager.add_section(section)
        return result
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/sections/{section_id}", response_model=Dict[str, Any])
async def update_section(
    section_id: int = Path(..., description="ID de la section à mettre à jour"),
    section: MemoireSection = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Met à jour une section existante du mémoire.
    """
    try:
        result = await memory_manager.update_section(section_id, section)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sections/{section_id}")
async def delete_section(
    section_id: int = Path(..., description="ID de la section à supprimer"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Supprime une section du mémoire.
    """
    try:
        await memory_manager.delete_section(section_id)
        return {"status": "success", "message": "Section supprimée avec succès"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sections", response_model=List[Dict[str, Any]])
async def get_sections(
    parent_id: Optional[int] = Query(None, description="ID du parent pour récupérer les sous-sections"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère les sections du mémoire, optionnellement filtrées par parent.
    """
    try:
        # Cette méthode doit être implémentée dans MemoryManager
        if parent_id is not None:
            sections = await memory_manager.get_sections_by_parent(parent_id)
        else:
            sections = await memory_manager.get_sections()
        return sections
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sections/{section_id}", response_model=Dict[str, Any])
async def get_section(
    section_id: int = Path(..., description="ID de la section à récupérer"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère une section spécifique du mémoire.
    """
    try:
        section = await memory_manager.get_section(section_id)
        return section
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/outline", response_model=List[Dict[str, Any]])
async def get_outline(
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère la structure complète du plan du mémoire.
    """
    try:
        outline = await memory_manager.get_outline()
        return outline
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sections/{section_id}/save", response_model=Dict[str, Any])
async def save_section_content(
    section_id: int = Path(..., description="ID de la section à sauvegarder"),
    section_data: Dict[str, Any] = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Sauvegarde le contenu d'une section du mémoire.
    """
    try:
        # Vérifier que la section existe
        section = await memory_manager.get_section(section_id)
        
        # Mettre à jour le contenu
        section["content"] = section_data.get("content", "")
        
        # Sauvegarder
        success = await memory_manager.save_section(section)
        
        if success:
            return {"status": "success", "message": "Section sauvegardée avec succès", "section_id": section_id}
        else:
            raise HTTPException(status_code=500, detail="Échec de la sauvegarde de la section")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sections/{section_id}/link/{entry_id}")
async def link_entry_to_section(
    section_id: int = Path(..., description="ID de la section"),
    entry_id: int = Path(..., description="ID de l'entrée de journal"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Associe une entrée de journal à une section du mémoire.
    """
    try:
        # Cette méthode doit être implémentée dans MemoryManager
        await memory_manager.link_entry_to_section(section_id, entry_id)
        return {"status": "success", "message": "Entrée associée à la section avec succès"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de l'association d'une entrée à une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sections/{section_id}/link/{entry_id}")
async def unlink_entry_from_section(
    section_id: int = Path(..., description="ID de la section"),
    entry_id: int = Path(..., description="ID de l'entrée de journal"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Supprime l'association entre une entrée de journal et une section du mémoire.
    """
    try:
        # Cette méthode doit être implémentée dans MemoryManager
        await memory_manager.unlink_entry_from_section(section_id, entry_id)
        return {"status": "success", "message": "Association supprimée avec succès"}
    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'une association: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_sections(
    query: str = Query(..., description="Texte à rechercher"),
    limit: int = Query(3, description="Nombre maximum de résultats"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Recherche des sections du mémoire par similarité sémantique.
    """
    try:
        results = await memory_manager.search_relevant_sections(query, limit)
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")

@router.post("/initialize-structure", response_model=Dict[str, Any])
async def initialize_structure(
    memory_manager = Depends(get_memory_manager)
):
    """
    Initialise la structure du mémoire selon les exigences RNCP.
    """
    try:
        success = await memory_manager.initialize_rncp_structure()
        
        if success:
            return {"status": "success", "message": "Structure du mémoire initialisée avec succès"}
        else:
            raise HTTPException(status_code=500, detail="Échec de l'initialisation de la structure")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la structure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))