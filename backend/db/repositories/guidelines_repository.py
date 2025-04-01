"""
Repository pour les opérations liées aux règles d'écriture du mémoire
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging
import uuid

from db.database import get_db_connection
from db.models.db_models import MemoireGuideline

# Configuration du logger
logger = logging.getLogger(__name__)

class GuidelinesRepository:
    """Repository pour les règles et consignes du mémoire"""
    
    def __init__(self):
        self.conn = get_db_connection()
    
    def __del__(self):
        if self.conn:
            self.conn.close()
    
    def get_guidelines(self, is_active: bool = True, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupère les directives du mémoire
        
        Args:
            is_active: Si True, ne récupère que les directives actives
            category: Filtre par catégorie si spécifié
            
        Returns:
            Liste des directives
        """
        cursor = self.conn.cursor()
        
        query = '''
        SELECT id, titre, contenu, source_document, created_at, 
               last_modified, is_active, order_index, category, metadata
        FROM memoire_guidelines
        '''
        
        params = []
        conditions = []
        
        if is_active:
            conditions.append("is_active = 1")
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY order_index"
        
        cursor.execute(query, params)
        
        guidelines = []
        for row in cursor.fetchall():
            guideline = dict(row)
            # Convertir les métadonnées JSON
            if guideline.get('metadata'):
                try:
                    guideline['metadata'] = json.loads(guideline['metadata'])
                except json.JSONDecodeError:
                    guideline['metadata'] = {}
            else:
                guideline['metadata'] = {}
            
            guidelines.append(guideline)
        
        return guidelines
    
    def get_guideline_by_id(self, guideline_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une directive spécifique par son ID"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
        SELECT id, titre, contenu, source_document, created_at, 
               last_modified, is_active, order_index, category, metadata
        FROM memoire_guidelines
        WHERE id = ?
        ''', (guideline_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        guideline = dict(row)
        
        # Convertir les métadonnées JSON
        if guideline.get('metadata'):
            try:
                guideline['metadata'] = json.loads(guideline['metadata'])
            except json.JSONDecodeError:
                guideline['metadata'] = {}
        else:
            guideline['metadata'] = {}
        
        return guideline
    
    def create_guideline(self, guideline: MemoireGuideline) -> Dict[str, Any]:
        """Crée une nouvelle directive pour le mémoire"""
        cursor = self.conn.cursor()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convertir métadonnées en JSON
        metadata_json = json.dumps(guideline.metadata) if guideline.metadata else None
        
        cursor.execute('''
        INSERT INTO memoire_guidelines (
            id, titre, contenu, source_document, created_at, 
            last_modified, is_active, order_index, category, metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            guideline.id,
            guideline.titre,
            guideline.contenu,
            guideline.source_document,
            now,
            now,
            1 if guideline.is_active else 0,
            guideline.order,
            guideline.category,
            metadata_json
        ))
        
        self.conn.commit()
        
        # Récupérer la directive nouvellement créée
        return self.get_guideline_by_id(guideline.id)
    
    def update_guideline(self, guideline_id: str, guideline: MemoireGuideline) -> Optional[Dict[str, Any]]:
        """Met à jour une directive existante"""
        # Vérifier si la directive existe
        existing = self.get_guideline_by_id(guideline_id)
        if not existing:
            return None
        
        cursor = self.conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Convertir métadonnées en JSON
        metadata_json = json.dumps(guideline.metadata) if guideline.metadata else None
        
        cursor.execute('''
        UPDATE memoire_guidelines
        SET titre = ?, contenu = ?, source_document = ?, last_modified = ?,
            is_active = ?, order_index = ?, category = ?, metadata = ?
        WHERE id = ?
        ''', (
            guideline.titre,
            guideline.contenu,
            guideline.source_document,
            now,
            1 if guideline.is_active else 0,
            guideline.order,
            guideline.category,
            metadata_json,
            guideline_id
        ))
        
        self.conn.commit()
        
        # Récupérer la directive mise à jour
        return self.get_guideline_by_id(guideline_id)
    
    def delete_guideline(self, guideline_id: str) -> bool:
        """Supprime une directive"""
        # Vérifier si la directive existe
        existing = self.get_guideline_by_id(guideline_id)
        if not existing:
            return False
        
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM memoire_guidelines WHERE id = ?", (guideline_id,))
        
        self.conn.commit()
        return cursor.rowcount > 0
    
    def import_guideline_from_document(self, 
                                      title: str,
                                      document_content: str,
                                      source_document: str,
                                      category: str = "general") -> Dict[str, Any]:
        """
        Importe une directive à partir du contenu d'un document
        
        Args:
            title: Titre de la directive
            document_content: Contenu du document
            source_document: Nom du document source
            category: Catégorie de la directive
            
        Returns:
            La directive créée
        """
        # Créer la guideline
        guideline = MemoireGuideline(
            titre=title,
            contenu=document_content,
            source_document=source_document,
            category=category,
            is_active=True
        )
        
        return self.create_guideline(guideline)