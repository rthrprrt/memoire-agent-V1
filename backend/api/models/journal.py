# api/models/memoire.py
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, constr, validator, root_validator
import re

from api.models.base import TimestampedModel
from api.models.journal import JournalEntryOutput

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

class MemoireSectionInDB(MemoireSectionBase, TimestampedModel):
    """Modèle pour une section de mémoire en base de données"""
    id: int
    parent_id: Optional[int] = None
    derniere_modification: datetime

    class Config:
        orm_mode = True

class MemoireSectionOutput(MemoireSectionInDB):
    """Modèle pour la sortie d'une section de mémoire avec informations supplémentaires"""
    parent_titre: Optional[str] = None
    journal_entries: Optional[List[JournalEntryOutput]] = None
    content_preview: Optional[str] = None
    children: Optional[List['MemoireSectionOutput']] = None
    level: Optional[int] = 0

class OutlineItemBase(BaseModel):
    """Modèle de base pour un élément du plan"""
    id: int
    titre: str
    ordre: int

class OutlineItem(OutlineItemBase):
    """Modèle complet pour un élément du plan avec structure hiérarchique"""
    children: List['OutlineItem'] = []
    
    class Config:
        orm_mode = True

# Pour permettre la récursivité des références
OutlineItem.update_forward_refs()
MemoireSectionOutput.update_forward_refs()

class Outline(BaseModel):
    """Modèle pour le plan complet du mémoire"""
    sections: List[OutlineItem]
    total_sections: int
    total_with_content: int
    progress: float = 0.0

    @root_validator
    def compute_progress(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Calcule la progression du mémoire"""
        total = values.get("total_sections", 0)
        with_content = values.get("total_with_content", 0)
        if total > 0:
            values["progress"] = round(with_content / total * 100, 2)
        return values

class SectionLink(BaseModel):
    """Modèle pour lier une entrée de journal à une section"""
    section_id: int
    entry_id: int

class BibliographyReferenceBase(BaseModel):
    """Modèle de base pour une référence bibliographique"""
    type: str = Field(..., description="Type de référence (article, livre, site web, etc.)")
    title: str = Field(..., description="Titre de la référence")
    authors: Union[str, List[str]] = Field(..., description="Auteur(s) de la référence")
    year: Optional[int] = Field(None, description="Année de publication")
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

class BibliographyReferenceUpdate(BaseModel):
    """Modèle pour la mise à jour d'une référence bibliographique"""
    type: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[Union[str, List[str]]] = None
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

class BibliographyReference(BibliographyReferenceBase, TimestampedModel):
    """Modèle complet pour une référence bibliographique"""
    id: str
    citation: Optional[str] = None
    last_modified: datetime

    class Config:
        orm_mode = True

    @root_validator
    def format_citation(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Génère une citation formatée"""
        # Exemple simple - dans une version réelle, cela serait plus sophistiqué
        authors = values.get("authors", "")
        if isinstance(authors, list):
            if len(authors) > 3:
                author_text = f"{authors[0]} et al."
            else:
                author_text = ", ".join(authors)
        else:
            author_text = authors
            
        year = values.get("year", "")
        title = values.get("title", "")
        publisher = values.get("publisher", "")
        
        citation = f"{author_text} ({year}). {title}."
        if publisher:
            citation += f" {publisher}."
            
        values["citation"] = citation
        return values