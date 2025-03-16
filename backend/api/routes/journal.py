from fastapi import APIRouter, HTTPException, Depends, Query, Path, Form, UploadFile, File, BackgroundTasks
from typing import List, Optional
import logging
from datetime import datetime

from api.models.journal import (
    JournalEntryCreate, 
    JournalEntryUpdate, 
    JournalEntryOutput,
    JournalEntryList,
    Tag,
    Entreprise
)
from services.memory_manager import MemoryManager, get_memory_manager
from utils.pdf_extractor import process_pdf_file
from core.exceptions import DatabaseError, ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/entries", response_model=JournalEntryOutput)
async def add_journal_entry(
    entry: JournalEntryCreate,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Ajoute une entrée au journal de bord
    
    Cette fonction permet de créer une nouvelle entrée dans le journal avec du texte, une date et des tags optionnels.
    """
    try:
        result = await memory_manager.add_journal_entry(entry.dict())
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries", response_model=List[JournalEntryOutput])
async def get_journal_entries(
    start_date: Optional[str] = Query(None, description="Date de début (format YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin (format YYYY-MM-DD)"),
    entreprise_id: Optional[int] = Query(None, description="ID de l'entreprise"),
    type_entree: Optional[str] = Query(None, description="Type d'entrée (quotidien, projet, formation, réflexion)"),
    tag: Optional[str] = Query(None, description="Tag à filtrer"),
    limit: int = Query(50, description="Nombre maximum d'entrées à retourner"),
    offset: int = Query(0, description="Nombre d'entrées à sauter (pour la pagination)"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Liste les entrées du journal avec filtres optionnels
    
    Cette fonction permet de récupérer des entrées du journal en appliquant divers filtres.
    """
    try:
        entries = await memory_manager.get_journal_entries(
            start_date=start_date,
            end_date=end_date,
            entreprise_id=entreprise_id,
            type_entree=type_entree,
            tag=tag,
            limit=limit,
            offset=offset
        )
        return entries
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entrées: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries/{entry_id}", response_model=JournalEntryOutput)
async def get_journal_entry(
    entry_id: int = Path(..., description="ID de l'entrée à récupérer"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Récupère une entrée spécifique du journal
    
    Cette fonction permet de récupérer les détails d'une entrée de journal par son ID.
    """
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

@router.put("/entries/{entry_id}", response_model=JournalEntryOutput)
async def update_journal_entry(
    entry_id: int,
    entry: JournalEntryUpdate,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Met à jour une entrée existante du journal
    
    Cette fonction permet de modifier le contenu, les tags ou d'autres attributs d'une entrée existante.
    """
    try:
        result = await memory_manager.update_journal_entry(entry_id, entry.dict(exclude_unset=True))
        if not result:
            raise HTTPException(status_code=404, detail="Entrée non trouvée")
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour d'une entrée: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entries/{entry_id}")
async def delete_journal_entry(
    entry_id: int,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime une entrée du journal
    
    Cette fonction permet de supprimer définitivement une entrée du journal.
    """
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

@router.post("/import/pdf")
async def import_pdf(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Importe un fichier PDF et extrait son contenu sous forme d'entrées de journal
    
    Cette fonction permet d'analyser un document PDF et d'en extraire automatiquement des entrées de journal.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le PDF
        entries = process_pdf_file(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        
        # Ajouter entreprise_id si fourni
        if entreprise_id is not None:
            for entry in entries:
                entry["entreprise_id"] = entreprise_id
        
        # Ajouter les entrées à la base de données
        added_entries = []
        for entry_data in entries:
            entry = JournalEntryCreate(**entry_data)
            result = await memory_manager.add_journal_entry(entry.dict())
            if result:
                added_entries.append(result)
        
        return {
            "entries": added_entries,
            "message": f"{len(added_entries)} entrées ajoutées avec succès."
        }
        
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors du traitement du PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du PDF: {str(e)}")

@router.post("/import/pdf/analyze")
async def analyze_pdf(
    file: UploadFile = File(...),
):
    """
    Analyse un fichier PDF sans l'importer dans la base de données
    
    Cette fonction permet de prévisualiser les entrées qui seraient créées à partir d'un PDF.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le PDF
        entries = process_pdf_file(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        
        return entries
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse du PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du PDF: {str(e)}")

@router.get("/entreprises", response_model=List[Entreprise])
async def get_entreprises(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Liste toutes les entreprises
    
    Cette fonction permet de récupérer la liste des entreprises pour l'alternance.
    """
    try:
        return await memory_manager.get_entreprises()
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entreprises: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tags", response_model=List[Tag])
async def get_tags(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Liste tous les tags avec leur nombre d'occurrences
    
    Cette fonction permet de récupérer la liste des tags utilisés dans le journal.
    """
    try:
        return await memory_manager.get_tags()
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tags: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))