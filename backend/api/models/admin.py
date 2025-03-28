# api/models/admin.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, RootModel

from api.models.base import TimestampedModel

class SystemStatus(BaseModel):
    """Statut du système"""
    status: str = Field(..., description="État général du système (healthy, warning, error)")
    components: Dict[str, str] = Field({}, description="État de chaque composant")
    version: str = Field(..., description="Version du système")
    uptime: float = Field(..., description="Temps d'activité en secondes")
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None

class BackupBase(BaseModel):
    """Modèle de base pour une sauvegarde"""
    description: Optional[str] = None

class BackupCreate(BackupBase):
    """Modèle pour la création d'une sauvegarde"""
    pass

class Backup(BackupBase, TimestampedModel):
    """Modèle complet pour une sauvegarde"""
    id: str
    status: str
    file_path: Optional[str] = None
    size_bytes: Optional[int] = None
    size_mb: Optional[float] = None
    available: bool = True

    model_config = {
        "from_attributes": True
    }

class BackupList(BaseModel):
    """Liste de sauvegardes"""
    items: List[Backup]
    total: int

class RestoreRequest(BaseModel):
    """Requête pour restaurer une sauvegarde"""
    backup_id: str
    confirm: bool = Field(..., description="Confirmation de la restauration")

class RestoreResponse(BaseModel):
    """Réponse de restauration"""
    status: str
    message: str
    backup_id: str
    completed_at: Optional[datetime] = None

class CircuitBreakerStatus(BaseModel):
    """Statut d'un Circuit Breaker"""
    name: str
    state: str
    failure_count: int
    failure_threshold: int
    reset_timeout: int
    last_failure_time: Optional[datetime] = None

class CacheStatus(BaseModel):
    """Statut du cache"""
    enabled: bool
    size: int
    hit_rate: float
    items: Dict[str, Any]

class RouteParameter(BaseModel):
    """Paramètre d'une route API"""
    name: str
    type: str
    required: bool = True
    default: Optional[str] = None
    kind: str = "query"  # query, path, body, etc.

class RouteInfo(BaseModel):
    """Informations de base sur une route API"""
    path: str
    name: str
    methods: List[str]
    tags: List[str] = []

class RouteDetailedInfo(RouteInfo):
    """Informations détaillées sur une route API"""
    description: Optional[str] = None
    parameters: List[RouteParameter] = []
    response_model: Optional[str] = None
    response_schema: Optional[Dict[str, Any]] = None

class SystemInfoResponse(BaseModel):
    """Réponse pour les informations système"""
    datetime: str
    os: str
    python_version: str
    cpu_count: int
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    environment: Dict[str, Any]
    installed_packages: List[Dict[str, str]]
    database: Optional[Dict[str, Any]] = None
    database_error: Optional[str] = None

class DatabaseColumn(BaseModel):
    """Colonne d'une table de base de données"""
    name: str
    type: str
    notnull: bool
    dflt_value: Optional[str] = None
    pk: bool

class DatabaseIndex(BaseModel):
    """Index d'une table de base de données"""
    name: str
    unique: bool
    columns: List[str]

class DatabaseForeignKey(BaseModel):
    """Clé étrangère d'une table de base de données"""
    id: int
    seq: int
    table: str
    from_col: str = Field(..., alias="from")
    to_col: str = Field(..., alias="to")
    on_update: str
    on_delete: str
    match: str

    model_config = {
        "populate_by_name": True
    }

class DatabaseTable(BaseModel):
    """Table de base de données"""
    columns: List[DatabaseColumn]
    indices: List[DatabaseIndex] = []
    foreign_keys: List[DatabaseForeignKey] = []
    row_count: Any

class DatabaseStructure(RootModel):
    """Structure de la base de données"""
    root: Dict[str, DatabaseTable]
    
    # Pour maintenir la compatibilité avec le code existant
    def __getitem__(self, item):
        return self.root[item]
    
    def __iter__(self):
        return iter(self.root)
    
    def items(self):
        return self.root.items()

class DatabaseQueryRequest(BaseModel):
    """Requête pour exécuter une requête SQL"""
    query: str
    params: Optional[Dict[str, Any]] = None

class DatabaseQueryResponse(BaseModel):
    """Réponse d'une requête SQL"""
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    query: str