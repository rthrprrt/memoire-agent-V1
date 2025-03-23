"""
Modèles de données pour les sections du mémoire.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, constr
import re

from api.models.base import TimestampedModel

# Modèle de base pour les sections du mémoire
class MemoireSectionBase(BaseModel):
    """Modèle de base pour les sections du mémoire"""
    titre: constr(min_length=3, max_length=200)
    content: Optional[constr(max_length=50000)] = None
    ordre: int = Field(..., ge=0, lt=1000)
    parent_id: Optional[int] = None

    @field_validator('content')
    def content_must_be_safe(cls, v):
        """Vérifie que le contenu ne contient pas de code malveillant"""
        if v and re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

class MemoireSectionCreate(MemoireSectionBase):
    """Modèle pour la création d'une section du mémoire"""
    pass

class MemoireSectionUpdate(MemoireSectionBase):
    """Modèle pour la mise à jour d'une section du mémoire"""
    titre: Optional[constr(min_length=3, max_length=200)] = None
    ordre: Optional[int] = Field(None, ge=0, lt=1000)

class MemoireSectionInDB(MemoireSectionBase, TimestampedModel):
    """Modèle pour une section du mémoire en base de données"""
    id: int
    derniere_modification: datetime

class MemoireSectionOutput(MemoireSectionInDB):
    """Modèle pour les sorties d'API de section du mémoire"""
    journal_entry_ids: Optional[List[int]] = []
    content_preview: Optional[str] = None

    model_config = {
        "populate_by_name": True 
    }

class OutlineItem(BaseModel):
    """Modèle pour un élément du plan du mémoire"""
    id: int
    title: str
    ordre: int
    children: Optional[List['OutlineItem']] = []

class SectionLink(BaseModel):
    """Modèle pour un lien entre une section et une entrée de journal"""
    section_id: int
    entry_id: int

class Outline(BaseModel):
    """Modèle pour le plan complet du mémoire"""
    sections: List[OutlineItem]

# Modèles pour les références bibliographiques
class BibliographyReferenceBase(BaseModel):
    """Modèle de base pour les références bibliographiques"""
    type: str  # book, article, website, etc.
    title: str
    authors: str
    year: Optional[int] = None
    publisher: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    accessed_date: Optional[datetime] = None
    notes: Optional[str] = None

class BibliographyReferenceCreate(BibliographyReferenceBase):
    """Modèle pour la création d'une référence bibliographique"""
    pass

class BibliographyReferenceUpdate(BibliographyReferenceBase):
    """Modèle pour la mise à jour d'une référence bibliographique"""
    type: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None

class BibliographyReference(BibliographyReferenceBase, TimestampedModel):
    """Modèle pour une référence bibliographique complète"""
    id: str
    last_modified: datetime

# Classe de compatibilité pour les routes existantes
class MemoireSection(BaseModel):
    """Modèle pour les sections du mémoire (compatibilité)."""
    titre: constr(min_length=3, max_length=200)
    content: Optional[constr(max_length=50000)] = None
    ordre: int = Field(..., ge=0, lt=1000)
    parent_id: Optional[int] = None

    model_config = {
        "extra": "forbid" 
    }

    @field_validator('content')
    def content_must_be_safe(cls, v):
        """Vérifie que le contenu ne contient pas de code malveillant"""
        if v and re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v