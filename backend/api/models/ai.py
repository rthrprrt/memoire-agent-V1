# api/models/ai.py
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class GeneratePlanRequest(BaseModel):
    """Requête pour générer un plan de mémoire"""
    prompt: str = Field(..., description="Instructions pour la génération du plan")
    
    class Config:
        schema_extra = {
            "example": {
                "prompt": "Générer un plan de mémoire sur le thème de l'IA dans le marketing digital"
            }
        }

class GeneratePlanResponse(BaseModel):
    """Réponse de génération de plan"""
    plan: str
    sections_created: Optional[int] = None

class GenerateContentRequest(BaseModel):
    """Requête pour générer du contenu pour une section"""
    section_id: int = Field(..., description="ID de la section à remplir")
    prompt: Optional[str] = Field(None, description="Instructions supplémentaires pour la génération")
    use_journal: bool = Field(True, description="Utiliser le journal comme contexte")
    
    class Config:
        schema_extra = {
            "example": {
                "section_id": 1,
                "prompt": "Mettre l'accent sur les aspects éthiques"
            }
        }

class GenerateContentResponse(BaseModel):
    """Réponse de génération de contenu"""
    generated_content: str
    section_id: int
    sources: Optional[List[Dict[str, Any]]] = None

class ImproveTextRequest(BaseModel):
    """Requête pour améliorer un texte"""
    texte: str = Field(..., description="Texte à améliorer")
    mode: str = Field("grammar", description="Mode d'amélioration (grammar, style, conciseness)")
    
    class Config:
        schema_extra = {
            "example": {
                "texte": "Ce texte contient des erreur et pourrait être amélioré.",
                "mode": "grammar"
            }
        }

class ImproveTextResponse(BaseModel):
    """Réponse d'amélioration de texte"""
    improved_text: str
    changes_made: Optional[int] = None

class HallucinationCheckRequest(BaseModel):
    """Requête pour vérifier les hallucinations"""
    content: str = Field(..., description="Contenu à vérifier")
    context: Optional[Dict[str, Any]] = None

class HallucinationCheckResponse(BaseModel):
    """Réponse de vérification d'hallucinations"""
    has_hallucinations: bool
    confidence_score: float
    suspect_segments: List[Dict[str, Any]]
    verified_facts: List[Dict[str, Any]]
    corrected_content: Optional[str] = None

class AutoTaskRequest(BaseModel):
    """Requête pour exécuter une tâche IA automatique"""
    prompt: str = Field(..., description="Instruction à exécuter")
    system_prompt: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class AutoTaskResponse(BaseModel):
    """Réponse d'exécution de tâche IA"""
    result: str
    task_type: Optional[str] = None
    execution_time: Optional[float] = None