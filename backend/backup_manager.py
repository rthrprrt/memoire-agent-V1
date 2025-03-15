import os
import tarfile
import shutil
import tempfile
import time
import glob
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class BackupManager:
    """
    Gère les sauvegardes et restaurations de l'ensemble des données du mémoire.
    """
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.backup_dir = os.path.join(base_path, "backups")
        # Créer le répertoire de sauvegardes s'il n'existe pas
        os.makedirs(self.backup_dir, exist_ok=True)
    
    async def create_backup(self, description: str = None) -> Dict[str, Any]:
        """
        Crée une sauvegarde complète des données du mémoire.
        Args:
            description: Description optionnelle de la sauvegarde
        Returns:
            Informations sur la sauvegarde créée
        """
        try:
            # Générer un nom de fichier basé sur la date/heure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"memoire_backup_{timestamp}"
            backup_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")
            
            # Informations de métadonnées
            metadata = {
                "id": backup_name,
                "timestamp": datetime.now().isoformat(),
                "description": description or f"Sauvegarde automatique du {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
                "file_path": backup_path,
                "status": "pending"
            }
            
            # Sauvegarder les métadonnées
            metadata_path = os.path.join(self.backup_dir, f"{backup_name}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Créer le fichier tar.gz
            with tarfile.open(backup_path, "w:gz") as tar:
                # Sauvegarder la base de données SQLite
                sqlite_db = os.path.join(self.base_path, "memoire.db")
                if os.path.exists(sqlite_db):
                    # Créer une copie temporaire pour éviter les problèmes de verrouillage
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp_path = tmp.name
                        shutil.copy2(sqlite_db, tmp_path)
                        tar.add(tmp_path, arcname="memoire.db")
                        os.unlink(tmp_path)
                
                # Sauvegarder le dossier ChromaDB
                vectordb_path = os.path.join(self.base_path, "vectordb")
                if os.path.exists(vectordb_path):
                    tar.add(vectordb_path, arcname="vectordb")
                
                # Sauvegarder le dossier des médias
                media_path = os.path.join(self.base_path, "media")
                if os.path.exists(media_path):
                    tar.add(media_path, arcname="media")
                
                # Ajouter les autres fichiers JSON (sauf les métadonnées de backup)
                for json_file in glob.glob(os.path.join(self.base_path, "*.json")):
                    if not json_file.endswith("_backup.json"):
                        tar.add(json_file, arcname=os.path.basename(json_file))
            
            # Mettre à jour les métadonnées après la sauvegarde
            metadata["status"] = "completed"
            metadata["size_bytes"] = os.path.getsize(backup_path)
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Sauvegarde créée: {backup_path}")
            return metadata
        
        except Exception as e:
            logger.error(f"Erreur lors de la création de la sauvegarde: {str(e)}")
            if 'metadata' in locals() and 'metadata_path' in locals():
                metadata["status"] = "failed"
                metadata["error"] = str(e)
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
            raise
    
    async def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Restaure une sauvegarde précédente.
        Args:
            backup_id: ID de la sauvegarde à restaurer
        Returns:
            Informations sur la restauration
        """
        metadata_path = os.path.join(self.backup_dir, f"{backup_id}.json")
        if not os.path.exists(metadata_path):
            raise ValueError(f"Sauvegarde non trouvée: {backup_id}")
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        if metadata.get("status") != "completed":
            raise ValueError(f"La sauvegarde {backup_id} n'est pas complète (statut: {metadata.get('status')})")
        
        backup_path = metadata.get("file_path")
        if not os.path.exists(backup_path):
            raise ValueError(f"Fichier de sauvegarde non trouvé: {backup_path}")
        
        try:
            # Sauvegarde de l'état actuel avant restauration
            current_backup = await self.create_backup("Sauvegarde automatique avant restauration")
            
            restore_info = {
                "backup_id": backup_id,
                "timestamp": datetime.now().isoformat(),
                "source_backup": metadata,
                "previous_state_backup": current_backup,
                "status": "in_progress"
            }
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(path=temp_dir)
                
                # Remplacer les fichiers actuels par ceux extraits
                
                # Base de données SQLite
                sqlite_db = os.path.join(self.base_path, "memoire.db")
                temp_sqlite = os.path.join(temp_dir, "memoire.db")
                if os.path.exists(temp_sqlite):
                    if os.path.exists(sqlite_db):
                        os.remove(sqlite_db)
                    shutil.copy2(temp_sqlite, sqlite_db)
                
                # Dossier ChromaDB
                vectordb_path = os.path.join(self.base_path, "vectordb")
                temp_vectordb = os.path.join(temp_dir, "vectordb")
                if os.path.exists(temp_vectordb):
                    if os.path.exists(vectordb_path):
                        shutil.rmtree(vectordb_path)
                    shutil.copytree(temp_vectordb, vectordb_path)
                
                # Dossier des médias
                media_path = os.path.join(self.base_path, "media")
                temp_media = os.path.join(temp_dir, "media")
                if os.path.exists(temp_media):
                    if os.path.exists(media_path):
                        shutil.rmtree(media_path)
                    shutil.copytree(temp_media, media_path)
                
                # Autres fichiers JSON
                for json_file in glob.glob(os.path.join(temp_dir, "*.json")):
                    filename = os.path.basename(json_file)
                    target_path = os.path.join(self.base_path, filename)
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    shutil.copy2(json_file, target_path)
            
            restore_info["status"] = "completed"
            restore_info["completed_at"] = datetime.now().isoformat()
            logger.info(f"Sauvegarde {backup_id} restaurée avec succès")
            return restore_info
        
        except Exception as e:
            logger.error(f"Erreur lors de la restauration de la sauvegarde: {str(e)}")
            if 'restore_info' in locals():
                restore_info["status"] = "failed"
                restore_info["error"] = str(e)
            raise

    async def list_backups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Liste les sauvegardes disponibles.
        Args:
            limit: Nombre maximum de sauvegardes à retourner
        Returns:
            Liste des métadonnées de sauvegardes
        """
        backups = []
        metadata_files = glob.glob(os.path.join(self.backup_dir, "*.json"))
        for metadata_path in metadata_files:
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                if "file_path" in metadata and os.path.exists(metadata["file_path"]):
                    metadata["file_size_mb"] = round(os.path.getsize(metadata["file_path"]) / (1024 * 1024), 2)
                    metadata["available"] = True
                else:
                    metadata["available"] = False
                backups.append(metadata)
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture des métadonnées {metadata_path}: {str(e)}")
        backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return backups[:limit]
    
    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Supprime une sauvegarde.
        Args:
            backup_id: ID de la sauvegarde à supprimer
        Returns:
            Informations sur la suppression
        """
        metadata_path = os.path.join(self.backup_dir, f"{backup_id}.json")
        if not os.path.exists(metadata_path):
            raise ValueError(f"Sauvegarde non trouvée: {backup_id}")
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        backup_path = metadata.get("file_path")
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.remove(metadata_path)
        
        return {
            "backup_id": backup_id,
            "deleted_at": datetime.now().isoformat(),
            "status": "deleted"
        }
    
    async def auto_cleanup(self, max_age_days: int = 30, max_count: int = 10) -> Dict[str, Any]:
        """
        Nettoie automatiquement les anciennes sauvegardes.
        Args:
            max_age_days: Âge maximum en jours des sauvegardes à conserver
            max_count: Nombre maximum de sauvegardes à conserver
        Returns:
            Informations sur le nettoyage
        """
        backups = await self.list_backups(limit=1000)
        now = datetime.now()
        cutoff_date = now - timedelta(days=max_age_days)
        old_backups = []
        for backup in backups:
            if "timestamp" in backup:
                try:
                    backup_date = datetime.fromisoformat(backup["timestamp"])
                    if backup_date < cutoff_date:
                        old_backups.append(backup)
                except (ValueError, TypeError):
                    pass
        excess_backups = []
        if len(backups) > max_count:
            excess_backups = backups[max_count:]
        to_delete = {b["id"] for b in old_backups + excess_backups}
        deleted = []
        for backup_id in to_delete:
            try:
                result = await self.delete_backup(backup_id)
                deleted.append(result)
            except Exception as e:
                logger.warning(f"Erreur lors de la suppression de la sauvegarde {backup_id}: {str(e)}")
        return {
            "deleted_count": len(deleted),
            "deleted_backups": deleted,
            "total_remaining": len(backups) - len(deleted)
        }
