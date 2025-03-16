# api/models/__init__.py
from api.models.base import TimestampedModel, PaginatedResponse, ErrorResponse
from api.models.journal import (
    JournalEntryBase, JournalEntryCreate, JournalEntryUpdate, JournalEntryInDB, 
    JournalEntryOutput, JournalEntryList, TagBase, Tag, EntrepriseBase, 
    EntrepriseCreate, EntrepriseUpdate, Entreprise
)
from api.models.memoire import (
    MemoireSectionBase, MemoireSectionCreate, MemoireSectionUpdate, MemoireSectionInDB,
    MemoireSectionOutput, OutlineItem, Outline, SectionLink, BibliographyReferenceBase,
    BibliographyReferenceCreate, BibliographyReferenceUpdate, BibliographyReference
)
from api.models.ai import (
    GeneratePlanRequest, GeneratePlanResponse, GenerateContentRequest, 
    GenerateContentResponse, ImproveTextRequest, ImproveTextResponse,
    HallucinationCheckRequest, HallucinationCheckResponse, AutoTaskRequest,
    AutoTaskResponse
)
from api.models.export import (
    ExportOptions, ExportRequest, ExportResponse, ExportDocument, ExportDocumentList
)
from api.models.admin import (
    SystemStatus, BackupBase, BackupCreate, Backup, BackupList,
    RestoreRequest, RestoreResponse, CircuitBreakerStatus, CacheStatus
)

# Liste des modèles disponibles pour faciliter l'auto-documentation
__all__ = [
    # Base
    "TimestampedModel", "PaginatedResponse", "ErrorResponse",
    
    # Journal
    "JournalEntryBase", "JournalEntryCreate", "JournalEntryUpdate", "JournalEntryInDB", 
    "JournalEntryOutput", "JournalEntryList", "TagBase", "Tag", "EntrepriseBase", 
    "EntrepriseCreate", "EntrepriseUpdate", "Entreprise",
    
    # Mémoire
    "MemoireSectionBase", "MemoireSectionCreate", "MemoireSectionUpdate", "MemoireSectionInDB",
    "MemoireSectionOutput", "OutlineItem", "Outline", "SectionLink", "BibliographyReferenceBase",
    "BibliographyReferenceCreate", "BibliographyReferenceUpdate", "BibliographyReference",
    
    # IA
    "GeneratePlanRequest", "GeneratePlanResponse", "GenerateContentRequest", 
    "GenerateContentResponse", "ImproveTextRequest", "ImproveTextResponse",
    "HallucinationCheckRequest", "HallucinationCheckResponse", "AutoTaskRequest",
    "AutoTaskResponse",
    
    # Export
    "ExportOptions", "ExportRequest", "ExportResponse", "ExportDocument", "ExportDocumentList",
    
    # Admin
    "SystemStatus", "BackupBase", "BackupCreate", "Backup", "BackupList",
    "RestoreRequest", "RestoreResponse", "CircuitBreakerStatus", "CacheStatus"
]