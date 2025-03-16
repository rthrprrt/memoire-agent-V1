"""
Routeur FastAPI pour les opérations du journal de bord.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query, Path, File, UploadFile, Form
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from pydantic import BaseModel, constr, Field, validator
import re

from core.memory_manager import get_memory_manager
from utils.text_analysis import extract_automatic_tags

# Configuration du logger
logger = logging.getLogger(__name__)

# Création du routeur
router = APIRouter()

# Modèles de données
class JournalEntry(BaseModel):
    """Modèle pour les entrées du journal de bord."""
    date: datetime
    texte: constr(min_length=10, max_length=10000)
    entreprise_id: Optional[int] = None
    type_entree: Optional[str] = "quotidien"
    source_document: Optional[str] = None
    tags: Optional[List[constr(min_length=1, max_length=50)]] = None

    class Config:
        extra = "forbid"  # Interdire les champs supplémentaires non déclarés

    @validator('texte')
    def texte_must_be_safe(cls, v):
        """Vérifie que le texte ne contient pas de code malveillant"""
        if re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

    @validator('tags', each_item=True)
    def tag_must_be_valid(cls, v):
        """Vérifie que chaque tag est valide (lettres, chiffres, tirets, underscores et espaces autorisés)"""
        if not re.match(r'^[a-zA-Z0-9\-_\s]+$', v):
            raise ValueError(f"Tag invalide: {v}. Utiliser uniquement des lettres, chiffres, tirets et underscores")
        return v

class PDFImportResponse(BaseModel):
    """Modèle de réponse pour l'import PDF."""
    entries: List[Dict[str, Any]]
    message: str
    
    class Config:
        extra = "forbid"

# Routes API
@router.post("/entries", response_model=Dict[str, Any])
async def add_journal_entry(
    entry: JournalEntry = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Ajoute une nouvelle entrée au journal de bord.
    """
    try:
        result = await memory_manager.add_journal_entry(entry)
        return result
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout d'une entrée de journal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/entries/{entry_id}", response_model=Dict[str, Any])
async def update_journal_entry(
    entry_id: int = Path(..., description="ID de l'entrée à mettre à jour"),
    entry: JournalEntry = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Met à jour une entrée existante du journal de bord.
    """
    try:
        result = await memory_manager.update_journal_entry(entry_id, entry)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour d'une entrée de journal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entries/{entry_id}")
async def delete_journal_entry(
    entry_id: int = Path(..., description="ID de l'entrée à supprimer"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Supprime une entrée du journal de bord.
    """
    try:
        await memory_manager.delete_journal_entry(entry_id)
        return {"status": "success", "message": "Entrée supprimée avec succès"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la suppression d'une entrée de journal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries", response_model=List[Dict[str, Any]])
async def get_journal_entries(
    start_date: Optional[str] = Query(None, description="Date de début (format YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin (format YYYY-MM-DD)"),
    entreprise_id: Optional[int] = Query(None, description="ID de l'entreprise"),
    type_entree: Optional[str] = Query(None, description="Type d'entrée (quotidien, projet, formation, réflexion)"),
    tag: Optional[str] = Query(None, description="Tag à filtrer"),
    limit: int = Query(50, description="Nombre maximum d'entrées à retourner"),
    skip: int = Query(0, description="Nombre d'entrées à ignorer (pour la pagination)"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère les entrées du journal de bord avec filtres optionnels.
    """
    try:
        # Cette méthode doit être implémentée dans MemoryManager
        entries = await memory_manager.get_journal_entries(
            start_date=start_date,
            end_date=end_date,
            entreprise_id=entreprise_id,
            type_entree=type_entree,
            tag=tag,
            limit=limit,
            skip=skip
        )
        return entries
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entrées de journal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entries/{entry_id}", response_model=Dict[str, Any])
async def get_journal_entry(
    entry_id: int = Path(..., description="ID de l'entrée à récupérer"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère une entrée spécifique du journal de bord.
    """
    try:
        entry = await memory_manager.get_journal_entry(entry_id)
        return entry
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la récupération d'une entrée de journal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tags", response_model=List[Dict[str, Any]])
async def get_tags(
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère la liste des tags utilisés dans le journal de bord.
    """
    try:
        # Cette méthode doit être implémentée dans MemoryManager
        tags = await memory_manager.get_tags()
        return tags
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tags: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/pdf", response_model=PDFImportResponse)
async def import_pdf(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
    memory_manager = Depends(get_memory_manager)
):
    """
    Importe un fichier PDF et extrait son contenu sous forme d'entrées de journal.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Import du module d'extraction PDF
        from utils.pdf_extractor import process_pdf_file
        
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
        for entry in entries:
            # Convertir en modèle JournalEntry
            journal_entry = JournalEntry(**entry)
            result = await memory_manager.add_journal_entry(journal_entry)
            if result:
                added_entries.append(result)
        
        return {
            "entries": added_entries,
            "message": f"{len(added_entries)} entrées ajoutées avec succès."
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du PDF: {str(e)}")

@router.post("/import/pdf/analyze", response_model=List[Dict[str, Any]])
async def analyze_pdf(
    file: UploadFile = File(...)
):
    """
    Analyse un fichier PDF sans l'importer et retourne les entrées potentielles.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Import du module d'extraction PDF
        from utils.pdf_extractor import process_pdf_file
        
        # Traiter le PDF
        entries = process_pdf_file(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        
        return entries
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse du PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du PDF: {str(e)}")

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_entries(
    query: str = Query(..., description="Texte à rechercher"),
    limit: int = Query(5, description="Nombre maximum de résultats"),
    memory_manager = Depends(get_memory_manager)
):
    """
    Recherche des entrées de journal par similarité sémantique.
    """
    try:
        results = await memory_manager.search_relevant_journal(query, limit)
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")

@router.get("/entreprises", response_model=List[Dict[str, Any]])
async def get_entreprises(
    memory_manager = Depends(get_memory_manager)
):
    """
    Récupère la liste des entreprises.
    """
    try:
        # Cette méthode doit être implémentée dans MemoryManager
        entreprises = await memory_manager.get_entreprises()
        return entreprises
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des entreprises: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))