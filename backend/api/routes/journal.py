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
from utils.pdf_extractor import process_document
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

@router.post("/import/document")
async def import_document(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Importe un fichier (PDF ou DOCX) et extrait son contenu sous forme d'entrées de journal
    
    Cette fonction permet d'analyser un document et d'en extraire automatiquement des entrées de journal.
    """
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF ou DOCX.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le document
        entries = process_document(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail=f"Impossible d'extraire des entrées du document {file.filename}.")
        
        # Validation des entrées avant traitement
        valid_entries = []
        for entry in entries:
            # Vérifier que le texte a la longueur minimale requise
            if "texte" in entry and len(entry["texte"]) < 10:
                logger.warning(f"Entrée avec texte trop court ({len(entry['texte'])} caractères) - ajout de contenu")
                # Ajouter du contenu pour atteindre la longueur minimale
                entry["texte"] = entry["texte"] + "\n\n" + f"Note générée le {datetime.now().strftime('%d/%m/%Y')} à partir du document {file.filename}"
            
            # Vérifier à nouveau et s'assurer que toutes les propriétés requises sont présentes
            if "texte" in entry and "date" in entry and len(entry["texte"]) >= 10:
                valid_entries.append(entry)
            else:
                logger.error(f"Entrée invalide ignorée: {entry}")
        
        if not valid_entries:
            raise HTTPException(status_code=400, detail=f"Aucune entrée valide extraite du document {file.filename}.")
        
        entries = valid_entries
        logger.info(f"{len(entries)} entrées valides extraites du document")
        
        # Ajouter entreprise_id si fourni
        if entreprise_id is not None:
            for entry in entries:
                entry["entreprise_id"] = entreprise_id
        
        # Ajouter les entrées à la base de données
        added_entries = []
        for entry_data in entries:
            # Convertir la date string en objet datetime si nécessaire
            if isinstance(entry_data.get("date"), str):
                try:
                    # Convertir le format YYYY-MM-DD en objet datetime
                    entry_data["date"] = datetime.strptime(entry_data["date"], "%Y-%m-%d")
                except ValueError as e:
                    logger.error(f"Erreur de conversion de date: {e}")
                    continue  # Ignorer cette entrée et passer à la suivante
            
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
        logger.error(f"Erreur lors du traitement du document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du document: {str(e)}")

# Maintenir la route /import/pdf pour la compatibilité avec les versions précédentes
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
    return await import_document(file, entreprise_id, memory_manager)

@router.post("/import/document/analyze")
async def analyze_document(
    file: UploadFile = File(...),
):
    """
    Analyse un fichier (PDF ou DOCX) sans l'importer dans la base de données
    
    Cette fonction permet de prévisualiser les entrées qui seraient créées à partir d'un document.
    """
    if not (file.filename.lower().endswith('.pdf') or file.filename.lower().endswith('.docx')):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF ou DOCX.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le document
        entries = process_document(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail=f"Impossible d'extraire des entrées du document {file.filename}.")
        
        # Validation des entrées avant traitement
        valid_entries = []
        for entry in entries:
            # Vérifier que le texte a la longueur minimale requise
            if "texte" in entry and len(entry["texte"]) < 10:
                logger.warning(f"Entrée avec texte trop court ({len(entry['texte'])} caractères) - texte complété")
                # Ajouter du contenu pour atteindre la longueur minimale
                entry["texte"] = entry["texte"] + "\n\n" + f"Note analysée le {datetime.now().strftime('%d/%m/%Y')} - Document: {file.filename}"
            
            # S'assurer que toutes les propriétés requises sont présentes
            if "texte" in entry and "date" in entry and len(entry["texte"]) >= 10:
                valid_entries.append(entry)
            else:
                logger.error(f"Entrée invalide ignorée lors de l'analyse: {entry}")
        
        if not valid_entries:
            raise HTTPException(status_code=400, detail=f"Aucune entrée valide extraite du document {file.filename} lors de l'analyse.")
        
        entries = valid_entries
        
        # Pour chaque entrée, convertir la date au format ISO pour éviter des problèmes de sérialisation
        for entry in entries:
            if isinstance(entry.get("date"), str):
                try:
                    # Pour l'API, on peut laisser la date sous forme de string, mais au format ISO
                    date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
                    entry["date"] = date_obj.isoformat()
                except ValueError:
                    pass  # Garder la date dans son format original si la conversion échoue
            
            # Log du contenu pour le debug
            logger.info(f"Entrée d'analyse - Date: {entry.get('date')}, Texte: {entry.get('texte')[:50]}... ({len(entry.get('texte', ''))} caractères)")
        
        return entries
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse du document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du document: {str(e)}")

# Maintenir la route /import/pdf/analyze pour la compatibilité avec les versions précédentes
@router.post("/import/pdf/analyze")
async def analyze_pdf(
    file: UploadFile = File(...),
):
    """
    Analyse un fichier PDF sans l'importer dans la base de données
    
    Cette fonction permet de prévisualiser les entrées qui seraient créées à partir d'un PDF.
    """
    return await analyze_document(file)

@router.get("/entreprises", response_model=List[Entreprise])
async def get_entreprises(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Liste toutes les entreprises
    
    Cette fonction permet de récupérer la liste des entreprises pour l'alternance.
    """
    try:
        logger.debug("Début de la récupération des entreprises")
        entreprises = await memory_manager.get_entreprises()
        logger.debug(f"Récupération de {len(entreprises)} entreprises réussie")
        return entreprises
    except DatabaseError as e:
        logger.error(f"Erreur de base de données lors de la récupération des entreprises: {str(e)}")
        # Retourner une liste vide au lieu d'une erreur 500
        logger.warning("Retour d'une liste vide comme solution de secours suite à une erreur de base de données")
        return []
    except Exception as e:
        logger.error(f"Erreur non gérée lors de la récupération des entreprises: {str(e)}")
        # Tracer la pile d'erreur pour faciliter le débogage
        import traceback
        logger.error(f"Détail de l'erreur: {traceback.format_exc()}")
        # Retourner une liste vide au lieu d'une erreur 500
        logger.warning("Retour d'une liste vide comme solution de secours suite à une erreur non gérée")
        return []

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

@router.delete("/import/cleanup")
async def cleanup_all_imports(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime toutes les entrées de journal créées à partir de documents importés
    
    Cette fonction permet de nettoyer la base de données des entrées générées automatiquement.
    """
    try:
        deleted_count = await memory_manager.cleanup_document_imports()
        return {
            "status": "success", 
            "message": f"{deleted_count} entrées issues d'imports supprimées",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des imports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/import/document/{filename}")
async def cleanup_document_import(
    filename: str,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime les entrées de journal créées à partir d'un document spécifique
    
    Cette fonction permet de nettoyer la base de données des entrées issues d'un import particulier.
    """
    try:
        deleted_count = await memory_manager.cleanup_specific_import(filename)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Aucune entrée trouvée pour le document {filename}")
        return {
            "status": "success", 
            "message": f"{deleted_count} entrées issues de l'import '{filename}' supprimées",
            "deleted_count": deleted_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage de l'import '{filename}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entries/cleanup/date")
async def cleanup_entries_by_date(
    start_date: Optional[str] = Query(None, description="Date de début (format YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin (format YYYY-MM-DD)"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime les entrées de journal dans une plage de dates
    
    Cette fonction permet de nettoyer la base de données des entrées par date.
    Au moins une des deux dates (début ou fin) doit être spécifiée.
    """
    if not start_date and not end_date:
        raise HTTPException(status_code=400, detail="Au moins une date (début ou fin) doit être spécifiée")
        
    try:
        deleted_count = await memory_manager.cleanup_entries_by_date(start_date, end_date)
        
        # Construire un message descriptif en fonction des dates fournies
        if start_date and end_date:
            message = f"{deleted_count} entrées entre le {start_date} et le {end_date} supprimées"
        elif start_date:
            message = f"{deleted_count} entrées à partir du {start_date} supprimées"
        else:
            message = f"{deleted_count} entrées jusqu'au {end_date} supprimées"
            
        return {
            "status": "success", 
            "message": message,
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des entrées par date: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entries/cleanup/all")
async def cleanup_all_entries(
    confirm: bool = Query(False, description="Confirmation de suppression de toutes les entrées"),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Supprime TOUTES les entrées de journal
    
    ATTENTION: Cette opération est irréversible et supprimera toutes les entrées, pas seulement les imports.
    Le paramètre 'confirm' doit être explicitement défini à True pour exécuter cette opération.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Cette opération est dangereuse. Pour confirmer, ajoutez le paramètre ?confirm=true"
        )
        
    try:
        deleted_count = await memory_manager.cleanup_all_entries()
        return {
            "status": "success", 
            "message": f"{deleted_count} entrées supprimées (base de données vidée)",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de toutes les entrées: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/import/sources")
async def get_import_sources(
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Liste tous les documents sources utilisés pour les imports
    
    Cette fonction permet de récupérer la liste des noms de fichiers ayant servi à des imports.
    """
    try:
        sources = await memory_manager.get_import_sources()
        return sources
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sources d'import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))