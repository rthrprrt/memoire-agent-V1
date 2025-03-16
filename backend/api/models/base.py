# api/models/base.py
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator, root_validator

class TimestampedModel(BaseModel):
    """Modèle de base avec horodatage"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @root_validator
    def set_timestamps(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Définit les horodatages automatiquement si non fournis"""
        now = datetime.now()
        if values.get("created_at") is None:
            values["created_at"] = now
        if values.get("updated_at") is None:
            values["updated_at"] = now
        return values

class PaginatedResponse(BaseModel):
    """Modèle pour les réponses paginées"""
    items: List[Any]
    total: int = 0
    page: int = 1
    size: int = 50
    pages: int = 1

    @root_validator
    def compute_pages(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule le nombre de pages"""
        total = values.get("total", 0)
        size = max(1, values.get("size", 50))
        values["pages"] = (total + size - 1) // size
        return values

class ErrorResponse(BaseModel):
    """Modèle pour les messages d'erreur"""
    detail: str
    code: Optional[str] = None
    location: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)