# api/models/base.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class TimestampedModel(BaseModel):
    """Modèle de base avec horodatage"""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode='before')
    def set_timestamps(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Définit les horodatages automatiquement si non fournis"""
        now = datetime.now()
        if isinstance(data, dict):
            if data.get("created_at") is None:
                data["created_at"] = now
            if data.get("updated_at") is None:
                data["updated_at"] = now
        return data


class PaginatedResponse(BaseModel):
    """Modèle pour les réponses paginées"""

    items: List[Any]
    total: int = 0
    page: int = 1
    size: int = 50
    pages: int = 1

    @model_validator(mode='before')
    def compute_pages(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule le nombre de pages"""
        if isinstance(data, dict):
            total = data.get("total", 0)
            size = max(1, data.get("size", 50))
            data["pages"] = (total + size - 1) // size
        return data


class ErrorResponse(BaseModel):
    """Modèle pour les messages d'erreur"""

    detail: str
    code: Optional[str] = None
    location: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
