from fastapi import APIRouter, HTTPException, Depends, Path, Query, Body
from typing import List, Optional, Dict, Any
import logging

from api.models.memoire import (
    MemoireSectionCreate, 
    MemoireSectionUpdate, 
    MemoireSectionOutput,
    OutlineItem,
    Outline,
    SectionLink,
    BibliographyReference,
    BibliographyReferenceCreate
)
from services.memory_manager import MemoryManager, get_memory_manager
from core.exceptions import DatabaseError, ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/sections", response_model=MemoireSectionOutput)
async def add_memoire_section(
    section: MemoireSectionCreate,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Ajoute une section au mémoire
    
    Cette fonction permet de créer une nouvelle section dans le mémoire professionnel.
    """
    try:
        result = await memory_manager.add_memoire_section(section.dict())
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sections", response_model=List[MemoireSectionOutput])
async def get_memoire_sections(
    parent_id: Optional[int] = Query(None, description="ID de la section parente"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Récupère les sections du mémoire
    
    Cette fonction permet de récupérer les sections au niveau racine ou les sous-sections d'une section parente.
    """
    try:
        return await memory_manager.get_memoire_sections(parent_id)
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sections/{section_id}", response_model=MemoireSectionOutput)
async def get_memoire_section(
    section_id: int = Path(..., description="ID de la section à récupérer"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Récupère une section spécifique du mémoire
    
    Cette fonction permet de récupérer les détails d'une section par son ID.
    """
    try:
        section = await memory_manager.get_memoire_section(section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section non trouvée")
        return section
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/sections/{section_id}", response_model=MemoireSectionOutput)
async def update_memoire_section(
    section_id: int = Path(..., description="ID de la section à mettre à jour"),
    section: MemoireSectionUpdate = Body(...),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Met à jour une section du mémoire
    
    Cette fonction permet de modifier le titre, le contenu ou d'autres attributs d'une section existante.
    """
    try:
        result = await memory_manager.update_memoire_section(section_id, section.dict(exclude_unset=True))
        if not result:
            raise HTTPException(status_code=404, detail="Section non trouvée")
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sections/{section_id}")
async def delete_memoire_section(
    section_id: int = Path(..., description="ID de la section à supprimer"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime une section du mémoire
    
    Cette fonction permet de supprimer définitivement une section et ses enfants.
    """
    try:
        success = await memory_manager.delete_memoire_section(section_id)
        if not success:
            raise HTTPException(status_code=404, detail="Section non trouvée")
        return {"status": "success", "message": "Section supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/outline", response_model=Outline)
async def get_outline(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Récupère la structure hiérarchique complète du plan du mémoire
    
    Cette fonction retourne le plan du mémoire avec toutes les sections organisées hiérarchiquement.
    """
    try:
        return await memory_manager.get_outline()
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sections/{section_id}/entries/{entry_id}")
async def link_entry_to_section(
    section_id: int = Path(..., description="ID de la section"),
    entry_id: int = Path(..., description="ID de l'entrée de journal"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Associe une entrée de journal à une section du mémoire
    
    Cette fonction permet d'établir un lien entre une entrée du journal et une section du mémoire.
    """
    try:
        success = await memory_manager.link_entry_to_section(section_id, entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Section ou entrée non trouvée")
        return {"status": "success", "message": "Entrée associée à la section avec succès"}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de l'association d'une entrée à une section: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sections/{section_id}/entries/{entry_id}")
async def unlink_entry_from_section(
    section_id: int = Path(..., description="ID de la section"),
    entry_id: int = Path(..., description="ID de l'entrée de journal"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime l'association entre une entrée de journal et une section du mémoire
    
    Cette fonction permet de retirer le lien entre une entrée du journal et une section du mémoire.
    """
    try:
        success = await memory_manager.unlink_entry_from_section(section_id, entry_id)
        if not success:
            raise HTTPException(status_code=404, detail="Association non trouvée")
        return {"status": "success", "message": "Association supprimée avec succès"}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de l'association: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bibliography", response_model=List[BibliographyReference])
async def get_bibliographie(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Récupère toutes les références bibliographiques
    
    Cette fonction permet de lister toutes les références bibliographiques du mémoire.
    """
    try:
        return await memory_manager.get_bibliographie()
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des références: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bibliography", response_model=BibliographyReference)
async def add_bibliographie_reference(
    reference: BibliographyReferenceCreate,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Ajoute une référence bibliographique
    
    Cette fonction permet d'ajouter une nouvelle référence à la bibliographie du mémoire.
    """
    try:
        return await memory_manager.add_bibliographie_reference(reference.dict())
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une référence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))