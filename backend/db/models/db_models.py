from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json
import uuid

class BaseDBModel:
    """Modèle de base pour les objets de la base de données"""
    
    @classmethod
    def from_row(cls, row: Dict[str, Any]):
        """Crée une instance à partir d'une ligne de base de données"""
        if row is None:
            return None
        return cls(**dict(row))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'instance en dictionnaire"""
        return self.__dict__
    
    @staticmethod
    def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
        """Sérialise un datetime en chaîne ISO"""
        return dt.isoformat() if dt else None
    
    @staticmethod
    def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
        """Parse une chaîne ISO en datetime"""
        return datetime.fromisoformat(dt_str) if dt_str else None

class JournalEntry(BaseDBModel):
    """Modèle pour une entrée de journal"""
    
    def __init__(self, 
                 id: int = None,
                 date: Union[str, datetime] = None,
                 texte: str = "",
                 entreprise_id: Optional[int] = None,
                 type_entree: str = "quotidien",
                 source_document: Optional[str] = None,
                 created_at: Union[str, datetime] = None,
                 tags: Optional[List[str]] = None,
                 entreprise_nom: Optional[str] = None,
                 **kwargs):
        self.id = id
        self.date = date if isinstance(date, datetime) else self.parse_datetime(date)
        self.texte = texte
        self.content = texte  # Pour compatibilité
        self.entreprise_id = entreprise_id
        self.type_entree = type_entree
        self.source_document = source_document
        self.created_at = created_at if isinstance(created_at, datetime) else self.parse_datetime(created_at)
        self.tags = tags or []
        self.entreprise_nom = entreprise_nom

class MemoireSection(BaseDBModel):
    """Modèle pour une section de mémoire"""
    
    def __init__(self,
                 id: int = None,
                 titre: str = "",
                 contenu: Optional[str] = None,
                 ordre: int = 0,
                 parent_id: Optional[int] = None,
                 derniere_modification: Union[str, datetime] = None,
                 parent_titre: Optional[str] = None,
                 content_preview: Optional[str] = None,
                 children: Optional[List[Dict[str, Any]]] = None,
                 journal_entries: Optional[List[Dict[str, Any]]] = None,
                 level: int = 0,
                 **kwargs):
        self.id = id
        self.titre = titre
        self.contenu = contenu
        self.ordre = ordre
        self.parent_id = parent_id
        self.derniere_modification = derniere_modification if isinstance(derniere_modification, datetime) else self.parse_datetime(derniere_modification)
        self.parent_titre = parent_titre
        self.content_preview = content_preview
        self.children = children or []
        self.journal_entries = journal_entries or []
        self.level = level

class BibliographyReference(BaseDBModel):
    """Modèle pour une référence bibliographique"""
    
    def __init__(self,
                 id: str = None,
                 type: str = "",
                 title: str = "",
                 authors: Union[str, List[str]] = "",
                 year: Optional[int] = None,
                 publisher: Optional[str] = None,
                 journal: Optional[str] = None,
                 volume: Optional[str] = None,
                 issue: Optional[str] = None,
                 pages: Optional[str] = None,
                 url: Optional[str] = None,
                 doi: Optional[str] = None,
                 accessed_date: Union[str, datetime] = None,
                 notes: Optional[str] = None,
                 last_modified: Union[str, datetime] = None,
                 citation: Optional[str] = None,
                 **kwargs):
        self.id = id
        self.type = type
        self.title = title
        
        # Gestion des auteurs (string ou liste)
        if isinstance(authors, str):
            try:
                self.authors = json.loads(authors)
            except (json.JSONDecodeError, TypeError):
                self.authors = authors
        else:
            self.authors = authors
            
        self.year = year
        self.publisher = publisher
        self.journal = journal
        self.volume = volume
        self.issue = issue
        self.pages = pages
        self.url = url
        self.doi = doi
        self.accessed_date = accessed_date if isinstance(accessed_date, datetime) else self.parse_datetime(accessed_date)
        self.notes = notes
        self.last_modified = last_modified if isinstance(last_modified, datetime) else self.parse_datetime(last_modified)
        self.citation = citation
        
        # Générer la citation si elle n'est pas fournie
        if not self.citation:
            self._generate_citation()
    
    def _generate_citation(self):
        """Génère une citation formatée à partir des données de référence"""
        # Formatage des auteurs
        if isinstance(self.authors, list):
            if len(self.authors) > 3:
                author_text = f"{self.authors[0]} et al."
            else:
                author_text = ", ".join(self.authors)
        else:
            author_text = str(self.authors) if self.authors else ""
        
        # Construction de la citation de base
        self.citation = f"{author_text} ({self.year or 'n.d.'}). {self.title or ''}."
        
        # Ajout du type spécifique selon le type de référence
        if self.type == "book" and self.publisher:
            self.citation += f" {self.publisher}."
        elif self.type == "article" and self.journal:
            journal_info = f" {self.journal}"
            if self.volume:
                journal_info += f", {self.volume}"
                if self.issue:
                    journal_info += f"({self.issue})"
            if self.pages:
                journal_info += f", {self.pages}"
            self.citation += journal_info + "."
        elif self.type == "website" and self.url:
            self.citation += f" {self.url}."
            if self.accessed_date:
                accessed_str = self.accessed_date.strftime('%d %B %Y') if isinstance(self.accessed_date, datetime) else self.accessed_date
                self.citation += f" Consulté le {accessed_str}."
                
class MemoireGuideline(BaseDBModel):
    """Modèle pour les règles et consignes du mémoire"""
    
    def __init__(self,
                 id: str = None,
                 titre: str = "",
                 contenu: str = "",
                 source_document: Optional[str] = None,
                 created_at: Union[str, datetime] = None,
                 last_modified: Union[str, datetime] = None,
                 is_active: bool = True,
                 order: int = 0,
                 category: str = "general",
                 metadata: Dict[str, Any] = None,
                 **kwargs):
        self.id = id or str(uuid.uuid4())
        self.titre = titre
        self.contenu = contenu
        self.source_document = source_document
        self.created_at = created_at if isinstance(created_at, datetime) else self.parse_datetime(created_at)
        self.last_modified = last_modified if isinstance(last_modified, datetime) else self.parse_datetime(last_modified)
        self.is_active = is_active
        self.order = order
        self.category = category
        self.metadata = metadata or {}