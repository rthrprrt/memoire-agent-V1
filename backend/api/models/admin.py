# api/models/admin.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

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