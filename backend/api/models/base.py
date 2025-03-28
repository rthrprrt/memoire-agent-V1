# api/models/base.py

from datetime import datetime
from typing import Any, Dict, List, Optional, Annotated
import json

from pydantic import BaseModel, Field, model_validator
from pydantic.json import timedelta_isoformat
from pydantic_core import core_schema

# Classe personnalisée pour gérer la sérialisation des dates au format YYYY-MM-DD
class DateOnly(datetime):
    """Classe personnalisée pour le type datetime qui sera sérialisé au format YYYY-MM-DD"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                # Essayer d'abord le format ISO standard
                return datetime.fromisoformat(v)
            except ValueError:
                try:
                    # Puis essayer le format YYYY-MM-DD
                    return datetime.strptime(v, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"Format de date invalide: {v}")
        raise ValueError(f"Type de date invalide: {type(v)}")
    
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        """Définit le schéma pour la validation et la sérialisation"""
        return core_schema.union_schema([
            # Conversion depuis string
            core_schema.string_schema(
                pattern=r'^\d{4}-\d{2}-\d{2}$',
                metadata={"description": "Date au format YYYY-MM-DD"},
                coerce_numbers_to_string=True,
            ),
            # Passage direct d'un datetime
            core_schema.is_instance_schema(datetime),
        ],
        json_schema_extra={"format": "date"},
        serialization=core_schema.plain_serializer_function_ser_schema(
            lambda dt: dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else dt
        ))
    
    def __str__(self):
        return self.strftime("%Y-%m-%d")


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
