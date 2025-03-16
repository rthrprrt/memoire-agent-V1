from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, constr, validator
import re

class MemoireSectionBase(BaseModel):
    """Modèle de base pour une section de mémoire"""
    titre: constr(min_length=3, max_length=200)
    contenu: Optional[constr(max_length=50000)] = None
    ordre: int = Field(..., ge=0, lt=1000)

    @validator('contenu')
    def contenu_must_be_safe(cls, v):
        """Vérifie que le contenu ne contient pas de code malveillant"""
        if v and re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

class MemoireSectionCreate(MemoireSectionBase):
    """Modèle pour la création d'une section de mémoire"""
    parent_id: Optional[int] = None

class MemoireSectionUpdate(BaseModel):
    """Modèle pour la mise à jour d'une section de mémoire"""
    titre: Optional[constr(min_length=3, max_length=200)] = None
    contenu: Optional[constr(max_length=50000)] = None
    ordre: Optional[int] = Field(None, ge=0, lt=1000)
    parent_id: Optional[int] = None

    @validator('contenu')
    def contenu_must_be_safe(cls, v):
        """Vérifie que le contenu ne contient pas de code malveillant"""
        if v and re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

class MemoireSectionInDB(MemoireSectionBase):
    """Modèle pour une section de mémoire en base de données"""
    id: int
    parent_id: Optional[int] = None
    derniere_modification: datetime

    class Config:
        orm_mode = True

class MemoireSectionOutput(MemoireSectionInDB):
    """Modèle pour la sortie d'une section de mémoire avec informations supplémentaires"""
    parent_titre: Optional[str] = None
    journal_entries: Optional[List[Dict[str, Any]]] = None
    content_preview: Optional[str] = None

class OutlineItem(BaseModel):
    """Item du plan du mémoire avec structure hiérarchique"""
    id: int
    titre: str
    ordre: int
    children: List['OutlineItem'] = []

    class Config:
        orm_mode = True

# Pour la récursivité des OutlineItem
OutlineItem.update_forward_refs()