import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from db.repositories.journal_repository import JournalRepository
from db.repositories.memoire_repository import MemoireRepository
from core.exceptions import DatabaseError, ValidationError
from utils.text_processing import AdaptiveTextSplitter

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Service qui coordonne les opérations entre les différents repositories
    et fournit une interface unifiée pour les fonctionnalités du mémoire.
    """
    
    def __init__(self, 
                 journal_repository = None,
                 memoire_repository = None):
        """
        Initialise le MemoryManager avec les repositories nécessaires.
        
        Args:
            journal_repository: Repository pour les entrées de journal
            memoire_repository: Repository pour les sections du mémoire
        """
        self.journal_repository = journal_repository or JournalRepository()
        self.memoire_repository = memoire_repository or MemoireRepository()
        self.text_splitter = AdaptiveTextSplitter()
    
    # --- Méthodes pour les entrées du journal ---
    
    async def add_journal_entry(self, entry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute une entrée au journal de bord
        
        Args:
            entry_data: Données de l'entrée à ajouter
            
        Returns:
            Dict: L'entrée ajoutée avec son ID et autres métadonnées
        """
        try:
            return await self.journal_repository.add_entry(entry_data)
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'une entrée de journal: {str(e)}")
            raise ValidationError(f"Erreur lors de l'ajout de l'entrée: {str(e)}")
    
    async def get_journal_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une entrée spécifique du journal
        
        Args:
            entry_id: ID de l'entrée à récupérer
            
        Returns:
            Dict: L'entrée complète ou None si introuvable
        """
        try:
            return await self.journal_repository.get_entry(entry_id)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération d'une entrée de journal: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération de l'entrée: {str(e)}")
    
    async def update_journal_entry(self, entry_id: int, entry_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Met à jour une entrée du journal
        
        Args:
            entry_id: ID de l'entrée à mettre à jour
            entry_data: Nouvelles données de l'entrée
            
        Returns:
            Dict: L'entrée mise à jour ou None si introuvable
        """
        try:
            return await self.journal_repository.update_entry(entry_id, entry_data)
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour d'une entrée de journal: {str(e)}")
            raise ValidationError(f"Erreur lors de la mise à jour de l'entrée: {str(e)}")
    
    async def delete_journal_entry(self, entry_id: int) -> bool:
        """
        Supprime une entrée du journal
        
        Args:
            entry_id: ID de l'entrée à supprimer
            
        Returns:
            bool: True si l'entrée a été supprimée, False si introuvable
        """
        try:
            return await self.journal_repository.delete_entry(entry_id)
        except Exception as e:
            logger.error(f"Erreur lors de la suppression d'une entrée de journal: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression de l'entrée: {str(e)}")
    
    async def get_journal_entries(self, 
                                 start_date: Optional[str] = None,
                                 end_date: Optional[str] = None,
                                 entreprise_id: Optional[int] = None,
                                 type_entree: Optional[str] = None,
                                 tag: Optional[str] = None,
                                 limit: int = 50,
                                 offset: int = 0) -> List[Dict[str, Any]]:
        """
        Récupère les entrées du journal avec filtres optionnels
        
        Args:
            start_date: Date de début (format YYYY-MM-DD)
            end_date: Date de fin (format YYYY-MM-DD)
            entreprise_id: ID de l'entreprise
            type_entree: Type d'entrée (quotidien, projet, etc.)
            tag: Tag à filtrer
            limit: Nombre maximum d'entrées à retourner
            offset: Nombre d'entrées à sauter (pour la pagination)
            
        Returns:
            List[Dict]: Liste des entrées correspondant aux critères
        """
        try:
            return await self.journal_repository.get_entries(
                start_date=start_date,
                end_date=end_date,
                entreprise_id=entreprise_id,
                type_entree=type_entree,
                tag=tag,
                limit=limit,
                offset=offset
            )
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des entrées de journal: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des entrées: {str(e)}")
    
    async def search_journal_entries(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche des entrées par similarité sémantique
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            List[Dict]: Liste des entrées les plus pertinentes
        """
        try:
            return await self.journal_repository.search_entries(query, limit)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'entrées de journal: {str(e)}")
            return []  # Retourner une liste vide en cas d'erreur pour éviter de bloquer l'UI
    
    async def get_entreprises(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des entreprises
        
        Returns:
            List[Dict]: Liste des entreprises
        """
        try:
            logger.debug("MemoryManager: Tentative de récupération des entreprises")
            entreprises = await self.journal_repository.get_entreprises()
            logger.debug(f"MemoryManager: {len(entreprises)} entreprises récupérées avec succès")
            return entreprises
        except Exception as e:
            logger.error(f"MemoryManager: Erreur lors de la récupération des entreprises: {str(e)}")
            # Ajouter plus de détails pour le débogage
            import traceback
            logger.error(f"MemoryManager: Détail de l'erreur: {traceback.format_exc()}")
            
            # Essayer de retourner une liste vide plutôt que de propager l'erreur
            logger.warning("MemoryManager: Retour d'une liste vide comme solution de secours")
            return []
    
    async def get_tags(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des tags avec leur nombre d'occurrences
        
        Returns:
            List[Dict]: Liste des tags
        """
        try:
            return await self.journal_repository.get_tags()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tags: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des tags: {str(e)}")
    
    async def cleanup_document_imports(self) -> int:
        """
        Supprime toutes les entrées de journal créées à partir de documents importés
        
        Returns:
            int: Nombre d'entrées supprimées
        """
        try:
            return await self.journal_repository.delete_entries_by_source()
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des imports: {str(e)}")
            raise DatabaseError(f"Erreur lors du nettoyage des imports: {str(e)}")
    
    async def cleanup_specific_import(self, filename: str) -> int:
        """
        Supprime les entrées de journal créées à partir d'un document spécifique
        
        Args:
            filename: Nom du fichier source
            
        Returns:
            int: Nombre d'entrées supprimées
        """
        try:
            return await self.journal_repository.delete_entries_by_source(filename)
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage de l'import '{filename}': {str(e)}")
            raise DatabaseError(f"Erreur lors du nettoyage de l'import '{filename}': {str(e)}")
    
    async def cleanup_entries_by_date(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
        """
        Supprime les entrées de journal dans une plage de dates
        
        Args:
            start_date: Date de début (format YYYY-MM-DD), optionnel
            end_date: Date de fin (format YYYY-MM-DD), optionnel
            
        Returns:
            int: Nombre d'entrées supprimées
        """
        try:
            return await self.journal_repository.delete_entries_by_date(start_date, end_date)
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des entrées par date: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression des entrées par date: {str(e)}")
    
    async def cleanup_all_entries(self) -> int:
        """
        Supprime toutes les entrées de journal
        
        Returns:
            int: Nombre d'entrées supprimées
        """
        try:
            return await self.journal_repository.delete_all_entries()
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de toutes les entrées: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression de toutes les entrées: {str(e)}")
    
    async def get_import_sources(self) -> List[Dict[str, Any]]:
        """
        Liste tous les documents sources utilisés pour les imports
        
        Returns:
            List[Dict]: Liste des sources d'import avec leur nombre d'entrées
        """
        try:
            return await self.journal_repository.get_import_sources()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des sources d'import: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des sources d'import: {str(e)}")
    
    # --- Méthodes pour les sections du mémoire ---
    
    async def add_memoire_section(self, section_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute une section au mémoire
        
        Args:
            section_data: Données de la section à ajouter
            
        Returns:
            Dict: La section ajoutée avec son ID et autres métadonnées
        """
        try:
            return await self.memoire_repository.add_section(section_data)
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'une section: {str(e)}")
            raise ValidationError(f"Erreur lors de l'ajout de la section: {str(e)}")
    
    async def get_memoire_section(self, section_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une section spécifique du mémoire
        
        Args:
            section_id: ID de la section à récupérer
            
        Returns:
            Dict: La section complète ou None si introuvable
        """
        try:
            return await self.memoire_repository.get_section(section_id)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération d'une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération de la section: {str(e)}")
    
    async def update_memoire_section(self, section_id: int, section_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Met à jour une section du mémoire
        
        Args:
            section_id: ID de la section à mettre à jour
            section_data: Nouvelles données de la section
            
        Returns:
            Dict: La section mise à jour ou None si introuvable
        """
        try:
            return await self.memoire_repository.update_section(section_id, section_data)
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour d'une section: {str(e)}")
            raise ValidationError(f"Erreur lors de la mise à jour de la section: {str(e)}")
    
    async def delete_memoire_section(self, section_id: int) -> bool:
        """
        Supprime une section du mémoire
        
        Args:
            section_id: ID de la section à supprimer
            
        Returns:
            bool: True si la section a été supprimée, False si introuvable
        """
        try:
            return await self.memoire_repository.delete_section(section_id)
        except Exception as e:
            logger.error(f"Erreur lors de la suppression d'une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression de la section: {str(e)}")
    
    async def get_memoire_sections(self, parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Récupère les sections du mémoire
        
        Args:
            parent_id: ID du parent (None pour les sections racines)
            
        Returns:
            List[Dict]: Liste des sections correspondantes
        """
        try:
            return await self.memoire_repository.get_sections(parent_id)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des sections: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des sections: {str(e)}")
    
    async def get_outline(self) -> Dict[str, Any]:
        """
        Récupère la structure complète du plan du mémoire
        
        Returns:
            Dict: Structure hiérarchique des sections avec statistiques
        """
        try:
            return await self.memoire_repository.get_outline()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du plan: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération du plan: {str(e)}")
    
    async def search_relevant_sections(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche des sections par similarité sémantique
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            List[Dict]: Liste des sections les plus pertinentes
        """
        try:
            return await self.memoire_repository.search_sections(query, limit)
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de sections: {str(e)}")
            return []  # Retourner une liste vide en cas d'erreur pour éviter de bloquer l'UI
    
    async def link_entry_to_section(self, section_id: int, entry_id: int) -> bool:
        """
        Lie une entrée de journal à une section
        
        Args:
            section_id: ID de la section
            entry_id: ID de l'entrée de journal
            
        Returns:
            bool: True si l'opération a réussi
        """
        try:
            return await self.memoire_repository.link_entry_to_section(section_id, entry_id)
        except Exception as e:
            logger.error(f"Erreur lors de l'association d'une entrée à une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de l'association: {str(e)}")
    
    async def unlink_entry_from_section(self, section_id: int, entry_id: int) -> bool:
        """
        Supprime l'association entre une entrée de journal et une section
        
        Args:
            section_id: ID de la section
            entry_id: ID de l'entrée de journal
            
        Returns:
            bool: True si l'opération a réussi
        """
        try:
            return await self.memoire_repository.unlink_entry_from_section(section_id, entry_id)
        except Exception as e:
            logger.error(f"Erreur lors de la suppression de l'association: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression de l'association: {str(e)}")
    
    # --- Méthodes pour la bibliographie ---
    
    async def get_bibliographie(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les références bibliographiques
        
        Returns:
            List[Dict]: Liste des références bibliographiques
        """
        try:
            return await self.memoire_repository.get_bibliographie()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des références: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des références: {str(e)}")
    
    async def add_bibliographie_reference(self, reference_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute une référence bibliographique
        
        Args:
            reference_data: Données de la référence à ajouter
            
        Returns:
            Dict: La référence ajoutée avec son ID
        """
        try:
            return await self.memoire_repository.add_bibliographie_reference(reference_data)
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout d'une référence: {str(e)}")
            raise ValidationError(f"Erreur lors de l'ajout de la référence: {str(e)}")

# Fonction pour l'injection de dépendance
_memory_manager = None

async def get_memory_manager() -> MemoryManager:
    """
    Retourne l'instance singleton du MemoryManager.
    
    Returns:
        MemoryManager: Instance du MemoryManager
    """
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager