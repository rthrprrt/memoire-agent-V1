"""
Modèles Pydantic pour les fonctionnalités de vérification d'hallucinations.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class VerificationRequest(BaseModel):
    """Modèle de requête pour la vérification d'hallucinations."""
    content: str = Field(..., description="Contenu à vérifier")
    context_ids: Optional[Dict[str, List[str]]] = Field(
        None, 
        description="IDs des sections et entrées de journal pour fournir du contexte"
    )
    options: Optional[Dict[str, Any]] = Field(
        None, 
        description="Options supplémentaires pour la vérification"
    )

class SuspectSegment(BaseModel):
    """Segment détecté comme une potentielle hallucination."""
    text: str = Field(..., description="Texte du segment")
    context: str = Field(..., description="Contexte entourant le segment")
    position: tuple = Field(..., description="Position (début, fin) dans le texte original")
    pattern_type: str = Field(..., description="Type de pattern détecté")
    verified: bool = Field(False, description="Si le segment a été vérifié")
    verification_source: Optional[str] = Field(None, description="Source de vérification si applicable")

class VerifiedFact(BaseModel):
    """Fait vérifié dans le texte."""
    text: str = Field(..., description="Texte du fait vérifié")
    verification_source: str = Field(..., description="Source de la vérification")
    confidence: float = Field(..., description="Niveau de confiance de la vérification")

class UncertainSegment(BaseModel):
    """Segment avec marqueurs d'incertitude."""
    text: str = Field(..., description="Texte du segment incertain")
    context: str = Field(..., description="Contexte entourant le segment")
    position: tuple = Field(..., description="Position (début, fin) dans le texte original")

class VerificationResponse(BaseModel):
    """Modèle de réponse pour la vérification d'hallucinations."""
    has_hallucinations: bool = Field(..., description="Si des hallucinations ont été détectées")
    confidence_score: float = Field(..., description="Score de confiance global (1.0 = confiance totale)")
    suspect_segments: List[Dict[str, Any]] = Field(..., description="Segments suspects détectés")
    verified_facts: List[Dict[str, Any]] = Field(..., description="Faits vérifiés comme corrects")
    uncertain_segments: List[Dict[str, Any]] = Field(..., description="Segments avec marqueurs d'incertitude")
    corrected_content: str = Field(..., description="Version corrigée du contenu")

class ImproveContentRequest(BaseModel):
    """Modèle de requête pour l'amélioration de contenu avec vérification."""
    content: str = Field(..., description="Contenu à améliorer")
    use_context: bool = Field(True, description="Si le contexte doit être automatiquement recherché")
    context_ids: Optional[Dict[str, List[str]]] = Field(
        None, 
        description="IDs des sections et entrées de journal pour fournir du contexte"
    )

class ImproveContentResponse(BaseModel):
    """Modèle de réponse pour l'amélioration de contenu."""
    improved_content: str = Field(..., description="Contenu amélioré")
    changes_made: bool = Field(..., description="Si des modifications ont été effectuées")
    confidence_score: float = Field(..., description="Score de confiance du contenu amélioré")
    suspect_count: int = Field(..., description="Nombre de segments suspects détectés")
    verified_count: int = Field(..., description="Nombre de faits vérifiés")