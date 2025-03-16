"""
Routes pour la vérification et la correction des hallucinations dans le contenu généré.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, Optional, List
import logging

from backend.api.hallucination import VerificationRequest, VerificationResponse, ImproveContentRequest
from core.memory_manager import get_memory_manager
from api.hallucination import HallucinationDetector

# Configuration du logger
logger = logging.getLogger(__name__)

# Création du routeur
router = APIRouter(tags=["Vérification d'hallucinations"])

@router.post("/verify", response_model=VerificationResponse)
async def verify_content(
    request: VerificationRequest = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Vérifie le contenu fourni pour détecter les potentielles hallucinations.
    
    - **content**: Le texte à vérifier
    - **context_ids**: IDs optionnels de sections et entrées de journal pour le contexte 
    - **options**: Options de vérification supplémentaires
    
    Retourne les résultats détaillés de la vérification.
    """
    try:
        detector = HallucinationDetector(memory_manager)
        
        # Si des IDs de contexte sont fournis, les récupérer
        context = None
        if request.context_ids:
            context = {"sections": [], "journal_entries": []}
            
            # Récupérer les sections
            section_ids = request.context_ids.get("sections", [])
            for section_id in section_ids:
                try:
                    section = await memory_manager.get_section(section_id)
                    if section:
                        context["sections"].append(section)
                except Exception as e:
                    logger.warning(f"Impossible de récupérer la section {section_id}: {str(e)}")
            
            # Récupérer les entrées de journal
            entry_ids = request.context_ids.get("journal_entries", [])
            for entry_id in entry_ids:
                try:
                    entry = await memory_manager.get_journal_entry(entry_id)
                    if entry:
                        context["journal_entries"].append(entry)
                except Exception as e:
                    logger.warning(f"Impossible de récupérer l'entrée {entry_id}: {str(e)}")
        
        # Effectuer la vérification
        results = await detector.check_content(request.content, context)
        
        return results
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification d'hallucinations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {str(e)}")

@router.get("/status")
async def get_verification_status(
    memory_manager = Depends(get_memory_manager)
):
    """
    Retourne des statistiques sur le système de vérification d'hallucinations.
    """
    try:
        detector = HallucinationDetector(memory_manager)
        status = await detector.get_verification_status()
        return status
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/clear-cache")
async def clear_verification_cache(
    memory_manager = Depends(get_memory_manager)
):
    """
    Vide le cache de vérifications d'hallucinations.
    """
    try:
        detector = HallucinationDetector(memory_manager)
        detector.clear_cache()
        return {"status": "success", "message": "Cache vidé avec succès"}
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/improve-content")
async def improve_content_with_verification(
    request: ImproveContentRequest = Body(...),
    memory_manager = Depends(get_memory_manager)
):
    """
    Vérifie et améliore automatiquement le contenu en corrigeant les hallucinations.
    """
    try:
        detector = HallucinationDetector(memory_manager)
        
        # Récupérer le contexte si demandé
        context = None
        if request.use_context:
            # Construire un contexte à partir du contenu
            keywords = detector._extract_keywords(request.content)
            search_query = " ".join(keywords[:10])
            
            # Rechercher du contenu pertinent dans les sections et le journal
            sections = await memory_manager.search_relevant_sections(search_query, limit=3)
            journal_entries = await memory_manager.search_relevant_journal(search_query, limit=5)
            
            context = {
                "sections": sections,
                "journal_entries": journal_entries
            }
        
        # Effectuer la vérification
        results = await detector.check_content(request.content, context)
        
        # Si des hallucinations sont détectées, retourner la version corrigée
        if results["has_hallucinations"]:
            return {
                "improved_content": results["corrected_content"],
                "changes_made": True,
                "confidence_score": results["confidence_score"],
                "suspect_count": len(results["suspect_segments"]),
                "verified_count": len(results["verified_facts"])
            }
        else:
            # Pas d'hallucinations, retourner le contenu original
            return {
                "improved_content": request.content,
                "changes_made": False,
                "confidence_score": results["confidence_score"],
                "suspect_count": 0,
                "verified_count": len(results["verified_facts"])
            }
            
    except Exception as e:
        logger.error(f"Erreur lors de l'amélioration du contenu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")