# api/models/export.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from api.models.base import TimestampedModel

class ExportOptions(BaseModel):
    """Options pour l'export de document"""
    format: str = Field("pdf", description="Format d'export (pdf, docx)")
    include_toc: bool = Field(True, description="Inclure une table des matières")
    include_bibliography: bool = Field(True, description="Inclure la bibliographie")
    include_appendices: bool = Field(True, description="Inclure les annexes")
    page_numbers: bool = Field(True, description="Inclure la numérotation des pages")
    cover_page: bool = Field(True, description="Inclure une page de couverture")
    document_title: str = Field("Mémoire de Mission Professionnelle", description="Titre du document")
    author_name: str = Field("", description="Nom de l'auteur")
    institution_name: str = Field("Epitech Digital School", description="Nom de l'institution")
    academic_year: str = Field("2024-2025", description="Année académique")
    margin_top_cm: float = Field(2.5, description="Marge supérieure en cm")
    margin_bottom_cm: float = Field(2.5, description="Marge inférieure en cm")
    margin_left_cm: float = Field(3.0, description="Marge gauche en cm")
    margin_right_cm: float = Field(2.5, description="Marge droite en cm")

class ExportRequest(BaseModel):
    """Requête pour exporter le mémoire"""
    options: ExportOptions = Field(default_factory=ExportOptions)
    sections: Optional[List[int]] = Field(None, description="IDs des sections à inclure (toutes si non spécifié)")

class ExportResponse(BaseModel):
    """Réponse d'exportation"""
    document_id: str
    format: str
    filename: str
    created_at: datetime
    file_size: int
    download_url: str

class ExportDocument(TimestampedModel):
    """Information sur un document exporté"""
    id: str
    title: str
    format: str
    filename: str
    file_path: str
    file_size: int
    download_url: Optional[str] = None
    available: bool = True

class ExportDocumentList(BaseModel):
    """Liste de documents exportés"""
    items: List[ExportDocument]
    total: int