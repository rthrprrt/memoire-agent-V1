from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Response
from typing import Dict, Any, Optional
import logging

from core.config import settings
from services.memory_manager import MemoryManager, get_memory_manager
from services.export_service import create_export, ExportOptions, get_export_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{format}", response_model=Dict[str, Any])
async def export_document(
    format: str,
    background_tasks: BackgroundTasks,
    title: Optional[str] = Query(None, description="Titre du document"),
    include_toc: bool = Query(True, description="Inclure une table des matières"),
    include_bibliography: bool = Query(True, description="Inclure la bibliographie"),
    include_appendices: bool = Query(True, description="Inclure les annexes"),
    cover_page: bool = Query(True, description="Inclure une page de couverture"),
    author_name: Optional[str] = Query(None, description="Nom de l'auteur"),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    export_service = Depends(get_export_service)
):
    """
    Exporte le mémoire dans un format spécifique (PDF ou DOCX)
    
    Cette fonction génère un document complet à partir du contenu du mémoire.
    """
    if format not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail=f"Format non supporté: {format}")
    
    try:
        # Créer les options d'export
        options = ExportOptions(
            format=format,
            include_toc=include_toc,
            include_bibliography=include_bibliography,
            include_appendices=include_appendices,
            cover_page=cover_page,
            document_title=title or "Mémoire de Mission Professionnelle",
            author_name=author_name or ""
        )
        
        # Générer le document en arrière-plan
        document_info = await create_export(
            memory_manager=memory_manager,
            export_service=export_service,
            options=options
        )
        
        return {
            "status": "success",
            "message": f"Export {format.upper()} généré avec succès",
            "document_info": document_info
        }
    except Exception as e:
        logger.error(f"Erreur lors de l'export au format {format}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")

@router.get("/download/{document_id}")
async def download_document(
    document_id: str,
    export_service = Depends(get_export_service)
):
    """
    Télécharge un document précédemment exporté
    
    Cette fonction récupère un document généré et le renvoie pour téléchargement.
    """
    try:
        document = await export_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document non trouvé")
        
        # Déterminer le type MIME
        content_type = "application/pdf" if document["format"] == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        return Response(
            content=document["content"],
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={document['filename']}"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement du document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du téléchargement: {str(e)}")