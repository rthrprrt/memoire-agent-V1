# api/models/hallucination.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class HallucinationSegment(BaseModel):
    """Modèle pour un segment suspect d'hallucination"""
    text: str = Field(..., description="Texte du segment")
    context: Optional[str] = Field(None, description="Contexte environnant")
    position: Optional[tuple] = Field(None, description="Position dans le texte (début, fin)")
    pattern_type: Optional[str] = Field(None, description="Type de pattern détecté")
    verified: bool = Field(False, description="Si le segment a été vérifié")
    verification_source: Optional[str] = Field(None, description="Source de la vérification")

class VerifiedFact(BaseModel):
    """Modèle pour un fait vérifié dans le texte"""
    text: str = Field(..., description="Texte du fait")
    confidence: float = Field(..., description="Niveau de confiance de la vérification")
    source: Optional[str] = Field(None, description="Source de la vérification")

class UncertainSegment(BaseModel):
    """Modèle pour un segment avec marqueurs d'incertitude"""
    text: str = Field(..., description="Texte du segment")
    context: str = Field(..., description="Contexte environnant")
    position: tuple = Field(..., description="Position dans le texte (début, fin)")

class HallucinationCheckRequest(BaseModel):
    """Requête pour vérifier les hallucinations"""
    content: str = Field(..., description="Contenu à vérifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexte additionnel pour la vérification")
    
    class Config:
        schema_extra = {
            "example": {
                "content": "Selon des études récentes, 87% des utilisateurs préfèrent cette approche.",
                "context": {
                    "sections": ["introduction", "méthodologie"],
                    "purpose": "academic"
                }
            }
        }

class HallucinationCheckResponse(BaseModel):
    """Réponse de vérification d'hallucinations"""
    has_hallucinations: bool = Field(..., description="Si des hallucinations ont été détectées")
    confidence_score: float = Field(..., description="Score de confiance global (0-1)")
    suspect_segments: List[Dict[str, Any]] = Field(..., description="Segments suspects d'hallucination")
    verified_facts: List[Dict[str, Any]] = Field(..., description="Faits vérifiés dans le contenu")
    uncertain_segments: Optional[List[Dict[str, Any]]] = Field(None, description="Segments avec marqueurs d'incertitude")
    corrected_content: Optional[str] = Field(None, description="Version corrigée du contenu")

class ImproveContentRequest(BaseModel):
    """Requête pour améliorer un contenu contenant des hallucinations"""
    content: str = Field(..., description="Contenu à améliorer")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexte additionnel")
    improvement_type: Optional[str] = Field("hallucinations", description="Type d'amélioration (hallucinations, style, etc.)")
    
    class Config:
        schema_extra = {
            "example": {
                "content": "Selon des études récentes, 87% des utilisateurs préfèrent cette approche.",
                "improvement_type": "hallucinations"
            }
        }

class ImproveContentResponse(BaseModel):
    """Réponse d'amélioration de contenu"""
    original_content: str = Field(..., description="Contenu original")
    corrected_content: str = Field(..., description="Contenu amélioré")
    changes_made: int = Field(..., description="Nombre de modifications apportées")
    improvement_notes: Optional[List[str]] = Field(None, description="Notes sur les améliorations apportées")