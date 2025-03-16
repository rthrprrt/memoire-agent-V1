# api/routes/hallucination.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional, List
import logging

from api.models.hallucination import (
    HallucinationCheckRequest,
    HallucinationCheckResponse,
    ImproveContentRequest,
    ImproveContentResponse
)
from services.memory_manager import MemoryManager, get_memory_manager
from hallucination_detector import HallucinationDetector

router = APIRouter()
logger = logging.getLogger(__name__)

# Singleton pour le détecteur d'hallucinations
_hallucination_detector = None

async def get_hallucination_detector(memory_manager: MemoryManager = Depends(get_memory_manager)) -> HallucinationDetector:
    """Obtient l'instance singleton du détecteur d'hallucinations"""
    global _hallucination_detector
    if _hallucination_detector is None:
        _hallucination_detector = HallucinationDetector(memory_manager)
    return _hallucination_detector

@router.post("/check-hallucinations", response_model=HallucinationCheckResponse)
async def check_hallucinations(
    request: HallucinationCheckRequest,
    detector: HallucinationDetector = Depends(get_hallucination_detector),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Vérifie un texte pour détecter d'éventuelles hallucinations
    
    Cette fonction analyse un contenu généré pour identifier et corriger les hallucinations potentielles.
    """
    try:
        # Enrichir le contexte si nécessaire
        context = request.context if request.context else {}
        
        # Si le contexte est vide, essayer de récupérer automatiquement un contexte pertinent
        if not context:
            query = " ".join([s for s in request.content.split()[:30]])  # Utiliser les 30 premiers mots comme requête
            
            # Rechercher des sections pertinentes
            relevant_sections = await memory_manager.search_relevant_sections(query, limit=3)
            
            # Rechercher des entrées de journal pertinentes
            journal_entries = await memory_manager.search_journal_entries(query, limit=3)
            
            # Ajouter au contexte
            context = {
                "sections": relevant_sections,
                "journal_entries": journal_entries
            }
        
        # Vérifier le contenu
        result = await detector.check_content(request.content, context)
        return HallucinationCheckResponse(**result)
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des hallucinations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {str(e)}")

@router.post("/improve-content", response_model=ImproveContentResponse)
async def improve_content(
    request: ImproveContentRequest,
    detector: HallucinationDetector = Depends(get_hallucination_detector),
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Améliore automatiquement un contenu en corrigeant les hallucinations
    
    Cette fonction vérifie et corrige les hallucinations dans un texte pour le rendre plus factuel.
    """
    try:
        # Enrichir le contexte si nécessaire
        context = request.context if request.context else {}
        
        # Si le contexte est vide, essayer de récupérer automatiquement un contexte pertinent
        if not context:
            query = " ".join([s for s in request.content.split()[:30]])
            relevant_sections = await memory_manager.search_relevant_sections(query, limit=3)
            journal_entries = await memory_manager.search_journal_entries(query, limit=3)
            context = {
                "sections": relevant_sections,
                "journal_entries": journal_entries
            }
        
        # D'abord vérifier le contenu pour détecter les hallucinations
        check_result = await detector.check_content(request.content, context)
        
        original_content = request.content
        corrected_content = check_result.get("corrected_content", original_content)
        
        # Si des hallucinations sont détectées mais qu'aucune correction n'a été faite
        if check_result.get("has_hallucinations", False) and corrected_content == original_content:
            # Utiliser le LLM pour améliorer le texte de façon plus générale
            from services.llm_service import execute_ai_task
            
            system_prompt = """Tu es un expert en vérification factuelle et en rédaction académique. 
            Ton objectif est d'améliorer le texte fourni en le rendant plus prudent, factuel et précis.
            Remplace tout chiffre précis par des approximations, reformule les affirmations catégoriques 
            en introduisant des nuances, et identifie clairement les sources lorsqu'elles sont citées."""
            
            user_prompt = f"""Voici un texte qui contient potentiellement des hallucinations ou des affirmations non vérifiables:
            
            "{original_content}"
            
            Améliore ce texte pour le rendre plus factuel, prudent et académiquement rigoureux. 
            Conserve le sens général mais remplace les affirmations non vérifiables par des formulations plus nuancées.
            """
            
            corrected_content = await execute_ai_task("improve", user_prompt, system_prompt)
        
        # Calculer le nombre de changements
        changes_made = sum(1 for i in range(min(len(original_content), len(corrected_content))) 
                          if original_content[i] != corrected_content[i])
        changes_made += abs(len(original_content) - len(corrected_content))
        
        # Générer des notes sur les améliorations
        improvement_notes = []
        for segment in check_result.get("suspect_segments", []):
            if segment.get("text") in original_content and segment.get("text") not in corrected_content:
                improvement_notes.append(f"Corrigé: '{segment.get('text')}'")
        
        return ImproveContentResponse(
            original_content=original_content,
            corrected_content=corrected_content,
            changes_made=changes_made,
            improvement_notes=improvement_notes or None
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'amélioration du contenu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'amélioration: {str(e)}")

@router.get("/statistics", response_model=Dict[str, Any])
async def get_statistics(
    detector: HallucinationDetector = Depends(get_hallucination_detector)
):
    """
    Récupère des statistiques sur les vérifications d'hallucinations
    
    Cette fonction renvoie des métriques sur les vérifications effectuées.
    """
    try:
        # Implémentation simplifiée des statistiques
        stats = {
            "total_checks": getattr(detector, "total_checks", 0),
            "hallucinations_detected": getattr(detector, "hallucinations_detected", 0),
            "avg_confidence_score": getattr(detector, "avg_confidence_score", 1.0),
            "common_patterns": getattr(detector, "common_patterns", {})
        }
        return stats
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))