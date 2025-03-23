"""
Modèles pour les fonctionnalités d'IA du mémoire.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class GeneratePlanRequest(BaseModel):
    """Modèle pour la requête de génération d'un plan de mémoire."""
    prompt: str

class GeneratePlanResponse(BaseModel):
    """Modèle pour la réponse de génération d'un plan de mémoire."""
    plan: str

class GenerateContentRequest(BaseModel):
    """Modèle pour la requête de génération de contenu pour une section."""
    section_id: int
    prompt: Optional[str] = None
    check_hallucinations: bool = True

class GenerateContentResponse(BaseModel):
    """Modèle pour la réponse de génération de contenu."""
    content: str
    section_id: int
    verification: Optional[Dict[str, Any]] = None

class ImproveTextRequest(BaseModel):
    """Modèle pour la requête d'amélioration d'un texte."""
    texte: str
    mode: str = "grammar"  # grammar, style, conciseness, expand

class ImproveTextResponse(BaseModel):
    """Modèle pour la réponse d'amélioration d'un texte."""
    improved_text: str

class HallucinationCheckRequest(BaseModel):
    """Modèle pour la requête de vérification d'hallucinations."""
    content: str
    context: Optional[Dict[str, Any]] = None
    threshold: float = 0.7

class HallucinationCheckResponse(BaseModel):
    """Modèle pour la réponse de vérification d'hallucinations."""
    has_hallucinations: bool
    confidence_score: float
    suspect_segments: List[Dict[str, Any]] = []
    corrected_content: Optional[str] = None

class AutoTaskRequest(BaseModel):
    """Modèle pour la requête d'exécution automatique d'une tâche."""
    prompt: str
    system_prompt: Optional[str] = None
    streaming: bool = False
    temperature: float = 0.7

class AutoTaskResponse(BaseModel):
    """Modèle pour la réponse d'exécution automatique d'une tâche."""
    result: str