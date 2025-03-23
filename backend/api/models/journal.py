"""
Modèles de données pour les entrées de journal.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, constr
import re

from api.models.base import TimestampedModel

# Modèle de base pour les tags
class TagBase(BaseModel):
    """Modèle de base pour les tags"""
    nom: constr(min_length=1, max_length=50)

    @field_validator('nom')
    def nom_must_be_valid(cls, v):
        """Vérifie que le tag est valide"""
        if not re.match(r'^[a-zA-Z0-9\-_\s]+$', v):
            raise ValueError(f"Tag invalide: {v}. Utiliser uniquement des lettres, chiffres, tirets et underscores")
        return v

class Tag(TagBase):
    """Modèle de tag complet avec ID"""
    id: int

# Modèle de base pour les entreprises
class EntrepriseBase(BaseModel):
    """Modèle de base pour les entreprises"""
    nom: constr(min_length=1, max_length=200)
    date_debut: datetime
    date_fin: Optional[datetime] = None
    description: Optional[str] = None

class EntrepriseCreate(EntrepriseBase):
    """Modèle pour la création d'une entreprise"""
    pass

class EntrepriseUpdate(EntrepriseBase):
    """Modèle pour la mise à jour d'une entreprise"""
    nom: Optional[constr(min_length=1, max_length=200)] = None
    date_debut: Optional[datetime] = None

class Entreprise(EntrepriseBase):
    """Modèle d'entreprise complet avec ID"""
    id: int

# Modèle de base pour les entrées de journal
class JournalEntryBase(BaseModel):
    """Modèle de base pour les entrées du journal de bord"""
    date: datetime
    texte: constr(min_length=10, max_length=10000)
    entreprise_id: Optional[int] = None
    type_entree: Optional[str] = "quotidien"
    source_document: Optional[str] = None
    tags: Optional[List[constr(min_length=1, max_length=50)]] = None

    @field_validator('texte')
    def texte_must_be_safe(cls, v):
        """Vérifie que le texte ne contient pas de code malveillant"""
        if re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

    @field_validator('tags')
    def tags_must_be_valid(cls, tags):
        """Vérifie que chaque tag est valide"""
        if tags is None:
            return tags
        for tag in tags:
            if not re.match(r'^[a-zA-Z0-9\-_\s]+$', tag):
                raise ValueError(f"Tag invalide: {tag}. Utiliser uniquement des lettres, chiffres, tirets et underscores")
        return tags

class JournalEntryCreate(JournalEntryBase):
    """Modèle pour la création d'une entrée de journal"""
    pass

class JournalEntryUpdate(JournalEntryBase):
    """Modèle pour la mise à jour d'une entrée de journal"""
    date: Optional[datetime] = None
    texte: Optional[constr(min_length=10, max_length=10000)] = None

class JournalEntryInDB(JournalEntryBase, TimestampedModel):
    """Modèle pour une entrée de journal en base de données"""
    id: int

class JournalEntryOutput(JournalEntryInDB):
    """Modèle pour les sorties d'API d'entrée de journal"""
    content: str = Field(..., alias="texte")
    entreprise_nom: Optional[str] = None
    similarity: Optional[float] = None

    model_config = {
        "populate_by_name": True
    }

class JournalEntryList(BaseModel):
    """Modèle pour une liste d'entrées de journal"""
    items: List[JournalEntryOutput]
    total: int

class JournalEntry(BaseModel):
    """Modèle pour les entrées du journal de bord (compatibilité)."""
    date: datetime
    texte: constr(min_length=10, max_length=10000)
    entreprise_id: Optional[int] = None
    type_entree: Optional[str] = "quotidien"
    source_document: Optional[str] = None
    tags: Optional[List[constr(min_length=1, max_length=50)]] = None

    model_config = {
        "extra": "forbid"  # Interdire les champs supplémentaires non déclarés
    }

    @field_validator('texte')
    def texte_must_be_safe(cls, v):
        """Vérifie que le texte ne contient pas de code malveillant"""
        if re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

    @field_validator('tags')
    def tags_must_be_valid(cls, tags):
        """Vérifie que chaque tag est valide (lettres, chiffres, tirets, underscores et espaces autorisés)"""
        if tags is None:
            return tags
        for tag in tags:
            if not re.match(r'^[a-zA-Z0-9\-_\s]+$', tag):
                raise ValueError(f"Tag invalide: {tag}. Utiliser uniquement des lettres, chiffres, tirets et underscores")
        return tags

class PDFImportResponse(BaseModel):
    """Modèle de réponse pour l'import PDF."""
    entries: List[Dict[str, Any]]
    message: str
    
    model_config = {
        "extra": "forbid"
    }