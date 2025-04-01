"""
Service pour la gestion centralisée de la mémoire et des données du mémoire.
"""

import os
import sqlite3
import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from pydantic import BaseModel, validator
from db.initializer import get_db_connection, journal_collection, sections_collection
from utils.text_processing import AdaptiveTextSplitter
from services.llm_service import get_llm_orchestrator

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Gestionnaire centralisé pour toutes les opérations liées au mémoire
    et aux entrées de journal.
    """
    def __init__(self, db_path: str = "data/memoire.db"):
        self.db_path = db_path
        self.text_splitter = AdaptiveTextSplitter()
        self.journal_collection = journal_collection
        self.sections_collection = sections_collection
        self.llm_orchestrator = get_llm_orchestrator()
        logger.info("MemoryManager initialisé")

    def get_connection(self):
        """Obtient une connexion à la base de données SQLite."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- MÉTHODES POUR LES ENTRÉES DU JOURNAL ---

    async def add_journal_entry(self, entry) -> dict:
        """
        Ajoute une nouvelle entrée au journal.
        
        Args:
            entry: Objet d'entrée du journal (JournalEntry)
            
        Returns:
            Dict contenant l'entrée ajoutée
        """
        def _add_entry():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Déterminer l'entreprise si non spécifiée
                entreprise_id = entry.entreprise_id
                if entreprise_id is None:
                    cursor.execute('''
                    SELECT id FROM entreprises 
                    WHERE date_debut <= ? AND (date_fin IS NULL OR date_fin >= ?)
                    ''', (entry.date, entry.date))
                    result = cursor.fetchone()
                    if result:
                        entreprise_id = result[0]
                
                # Extraire des tags automatiquement si non fournis
                tags = entry.tags
                if not tags:
                    from utils.text_analysis import extract_automatic_tags
                    tags = extract_automatic_tags(entry.texte)
                
                # Insérer l'entrée
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                INSERT INTO journal_entries (date, texte, entreprise_id, type_entree, source_document, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (entry.date, entry.texte, entreprise_id, entry.type_entree, entry.source_document, now))
                
                entry_id = cursor.lastrowid
                
                # Ajouter les tags
                if tags:
                    for tag in tags:
                        cursor.execute("SELECT id FROM tags WHERE nom = ?", (tag,))
                        result = cursor.fetchone()
                        if result:
                            tag_id = result[0]
                        else:
                            cursor.execute("INSERT INTO tags (nom) VALUES (?)", (tag,))
                            tag_id = cursor.lastrowid
                        cursor.execute("INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id))
                
                # Ajouter à la collection vectorielle pour la recherche
                try:
                    self.journal_collection.add(
                        documents=[entry.texte],
                        metadatas=[{"date": entry.date, "entry_id": entry_id}],
                        ids=[f"entry_{entry_id}"]
                    )
                except Exception as e:
                    logger.error(f"Erreur lors de l'ajout à ChromaDB: {str(e)}")
                    raise
                
                conn.commit()
                
                # Récupérer l'entrée complète
                cursor.execute('''
                SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, j.entreprise_id
                FROM journal_entries j
                WHERE j.id = ?
                ''', (entry_id,))
                
                inserted_entry = dict(cursor.fetchone())
                
                # Récupérer les tags
                cursor.execute('''
                SELECT t.nom FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ''', (entry_id,))
                
                inserted_entry['tags'] = [row[0] for row in cursor.fetchall()]
                
                return inserted_entry
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de l'ajout d'une entrée de journal: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_add_entry)

    async def update_journal_entry(self, entry_id: int, entry) -> dict:
        """
        Met à jour une entrée existante du journal.
        
        Args:
            entry_id: ID de l'entrée à mettre à jour
            entry: Nouvel objet d'entrée
            
        Returns:
            Dict contenant l'entrée mise à jour
        """
        def _update_entry():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Vérifier que l'entrée existe
                cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Entrée journal non trouvée: ID {entry_id}")
                
                # Mettre à jour l'entrée
                cursor.execute('''
                UPDATE journal_entries 
                SET date = ?, texte = ?, entreprise_id = ?, type_entree = ?, source_document = ?
                WHERE id = ?
                ''', (entry.date, entry.texte, entry.entreprise_id, entry.type_entree, entry.source_document, entry_id))
                
                # Mettre à jour les tags
                cursor.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
                if entry.tags:
                    for tag in entry.tags:
                        cursor.execute("SELECT id FROM tags WHERE nom = ?", (tag,))
                        result = cursor.fetchone()
                        if result:
                            tag_id = result[0]
                        else:
                            cursor.execute("INSERT INTO tags (nom) VALUES (?)", (tag,))
                            tag_id = cursor.lastrowid
                        cursor.execute("INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tag_id))
                
                # Mettre à jour dans la collection vectorielle
                try:
                    self.journal_collection.update(
                        documents=[entry.texte],
                        metadatas=[{"date": entry.date, "entry_id": entry_id}],
                        ids=[f"entry_{entry_id}"]
                    )
                except Exception as e:
                    logger.error(f"Erreur lors de la mise à jour dans ChromaDB: {str(e)}")
                    raise
                
                conn.commit()
                
                # Récupérer l'entrée mise à jour
                cursor.execute('''
                SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, j.entreprise_id
                FROM journal_entries j
                WHERE j.id = ?
                ''', (entry_id,))
                
                updated_entry = dict(cursor.fetchone())
                
                # Récupérer les tags
                cursor.execute('''
                SELECT t.nom FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ''', (entry_id,))
                
                updated_entry['tags'] = [row[0] for row in cursor.fetchall()]
                
                return updated_entry
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de la mise à jour d'une entrée de journal: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_update_entry)

    async def delete_journal_entry(self, entry_id: int) -> bool:
        """
        Supprime une entrée du journal.
        
        Args:
            entry_id: ID de l'entrée à supprimer
            
        Returns:
            True si l'opération a réussi
        """
        def _delete_entry():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Vérifier que l'entrée existe
                cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Entrée journal non trouvée: ID {entry_id}")
                
                # Supprimer l'entrée
                cursor.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
                
                # Supprimer de la collection vectorielle
                try:
                    self.journal_collection.delete(ids=[f"entry_{entry_id}"])
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression dans ChromaDB: {str(e)}")
                    raise
                
                conn.commit()
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de la suppression d'une entrée de journal: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_delete_entry)

    async def get_journal_entry(self, entry_id: int) -> Dict[str, Any]:
        """
        Récupère une entrée spécifique du journal.
        
        Args:
            entry_id: ID de l'entrée à récupérer
            
        Returns:
            Dict contenant l'entrée
        """
        def _get_entry():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, 
                       j.entreprise_id, e.nom as entreprise_nom
                FROM journal_entries j
                LEFT JOIN entreprises e ON j.entreprise_id = e.id
                WHERE j.id = ?
                ''', (entry_id,))
                
                entry = cursor.fetchone()
                if not entry:
                    raise ValueError(f"Entrée journal non trouvée: ID {entry_id}")
                
                result = dict(entry)
                
                # Récupérer les tags
                cursor.execute('''
                SELECT t.nom FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ''', (entry_id,))
                
                result['tags'] = [row[0] for row in cursor.fetchall()]
                
                return result
                
            except Exception as e:
                logger.error(f"Erreur lors de la récupération d'une entrée de journal: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_get_entry)

    async def search_relevant_journal(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche des entrées de journal pertinentes pour une requête.
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des entrées pertinentes
        """
        try:
            # Générer l'embedding pour la requête
            embedding = await self.llm_orchestrator.get_embeddings(query)
            
            # Rechercher dans la collection
            results = self.journal_collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            
            if not results or not results['ids'][0]:
                return []
            
            # Extraire les IDs des entrées trouvées
            entry_ids = [int(id.replace("entry_", "")) for id in results['ids'][0]]
            
            # Récupérer les détails complets des entrées
            entries = []
            for i, entry_id in enumerate(entry_ids):
                try:
                    entry = await self.get_journal_entry(entry_id)
                    
                    # Ajouter le score de similarité
                    if 'distances' in results:
                        entry['similarity'] = results['distances'][0][i]
                    
                    entries.append(entry)
                except ValueError:
                    # L'entrée a peut-être été supprimée
                    continue
            
            return entries
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de journal: {str(e)}")
            # En cas d'erreur, retourner une liste vide
            return []

    # --- MÉTHODES POUR LES SECTIONS DU MÉMOIRE ---

    async def get_section(self, section_id: int) -> Dict[str, Any]:
        """
        Récupère une section du mémoire par son ID.
        
        Args:
            section_id: ID de la section
            
        Returns:
            Dict contenant la section
        """
        def _get_section():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                cursor.execute('''
                SELECT id, titre, content, ordre, parent_id, derniere_modification
                FROM memoire_sections
                WHERE id = ?
                ''', (section_id,))
                
                section = cursor.fetchone()
                if not section:
                    raise ValueError(f"Section non trouvée: ID {section_id}")
                
                result = dict(section)
                
                # Récupérer les entrées de journal associées
                cursor.execute('''
                SELECT j.id
                FROM journal_entries j
                JOIN section_entries se ON j.id = se.entry_id
                WHERE se.section_id = ?
                ''', (section_id,))
                
                result['journal_entry_ids'] = [row[0] for row in cursor.fetchall()]
                
                return result
                
            except Exception as e:
                logger.error(f"Erreur lors de la récupération d'une section: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_get_section)

    async def add_section(self, section) -> Dict[str, Any]:
        """
        Ajoute une nouvelle section au mémoire.
        
        Args:
            section: Objet de section
            
        Returns:
            Dict contenant la section ajoutée
        """
        def _add_section():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Insérer la section
                cursor.execute('''
                INSERT INTO memoire_sections (titre, content, ordre, parent_id, derniere_modification)
                VALUES (?, ?, ?, ?, ?)
                ''', (section.titre, section.content, section.ordre, section.parent_id, now))
                
                section_id = cursor.lastrowid
                
                conn.commit()
                
                # Retourner la section complète
                return {
                    "id": section_id,
                    "titre": section.titre,
                    "content": section.content,
                    "ordre": section.ordre,
                    "parent_id": section.parent_id,
                    "derniere_modification": now
                }
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de l'ajout d'une section: {str(e)}")
                raise
            finally:
                conn.close()
                
        section_data = await asyncio.to_thread(_add_section)
        
        # Indexer le contenu pour la recherche
        try:
            await self._index_section_content(section_data)
            logger.info(f"Section {section_data['id']} indexée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la section: {str(e)}")
        
        return section_data

    async def update_section(self, section_id: int, section) -> Dict[str, Any]:
        """
        Met à jour une section existante du mémoire.
        
        Args:
            section_id: ID de la section à mettre à jour
            section: Nouvel objet de section
            
        Returns:
            Dict contenant la section mise à jour
        """
        def _update_section():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Vérifier que la section existe
                cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Section non trouvée: ID {section_id}")
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Mettre à jour la section
                cursor.execute('''
                UPDATE memoire_sections 
                SET titre = ?, content = ?, ordre = ?, parent_id = ?, derniere_modification = ?
                WHERE id = ?
                ''', (section.titre, section.content, section.ordre, section.parent_id, now, section_id))
                
                conn.commit()
                
                # Retourner la section mise à jour
                cursor.execute('''
                SELECT id, titre, content, ordre, parent_id, derniere_modification
                FROM memoire_sections
                WHERE id = ?
                ''', (section_id,))
                
                updated_section = dict(cursor.fetchone())
                
                return updated_section
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de la mise à jour d'une section: {str(e)}")
                raise
            finally:
                conn.close()
                
        section_data = await asyncio.to_thread(_update_section)
        
        # Mettre à jour l'index de recherche
        try:
            await self._index_section_content(section_data)
            logger.info(f"Index de section {section_id} mis à jour")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de l'index de section: {str(e)}")
        
        return section_data

    async def delete_section(self, section_id: int) -> bool:
        """
        Supprime une section du mémoire.
        
        Args:
            section_id: ID de la section à supprimer
            
        Returns:
            True si l'opération a réussi
        """
        def _delete_section():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Vérifier que la section existe
                cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
                if not cursor.fetchone():
                    raise ValueError(f"Section non trouvée: ID {section_id}")
                
                # Supprimer les associations avec les entrées de journal
                cursor.execute("DELETE FROM section_entries WHERE section_id = ?", (section_id,))
                
                # Supprimer la section
                cursor.execute("DELETE FROM memoire_sections WHERE id = ?", (section_id,))
                
                conn.commit()
                
                # Supprimer de l'index de recherche
                try:
                    self.sections_collection.delete(where={"section_id": section_id})
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression de l'index de section: {str(e)}")
                
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de la suppression d'une section: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_delete_section)

    async def get_outline(self) -> List[Dict[str, Any]]:
        """
        Récupère la structure complète du plan du mémoire.
        
        Returns:
            Liste des sections de premier niveau avec leurs sous-sections
        """
        def _get_outline():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Récupérer toutes les sections
                cursor.execute('''
                SELECT id, titre, parent_id, ordre
                FROM memoire_sections
                ORDER BY ordre
                ''')
                
                all_sections = [dict(row) for row in cursor.fetchall()]
                
                # Construire l'arborescence
                sections_by_id = {s["id"]: {"id": s["id"], "title": s["titre"], "ordre": s["ordre"]} for s in all_sections}
                root_sections = []
                
                for section in all_sections:
                    parent_id = section["parent_id"]
                    section_dict = sections_by_id[section["id"]]
                    
                    if parent_id is None:
                        root_sections.append(section_dict)
                    else:
                        if "children" not in sections_by_id[parent_id]:
                            sections_by_id[parent_id]["children"] = []
                        sections_by_id[parent_id]["children"].append(section_dict)
                
                # Trier par ordre
                root_sections.sort(key=lambda x: x["ordre"])
                for section_id, section in sections_by_id.items():
                    if "children" in section:
                        section["children"].sort(key=lambda x: x["ordre"])
                
                return root_sections
                
            except Exception as e:
                logger.error(f"Erreur lors de la récupération du plan: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_get_outline)

    async def save_section(self, section: Dict[str, Any]) -> bool:
        """
        Sauvegarde une section mise à jour.
        
        Args:
            section: Dictionnaire de la section à sauvegarder
            
        Returns:
            True si l'opération a réussi
        """
        def _save_section():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "UPDATE memoire_sections SET content = ?, derniere_modification = ? WHERE id = ?", 
                    (section["content"], now, section["id"])
                )
                
                conn.commit()
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de la sauvegarde de la section: {str(e)}")
                raise
            finally:
                conn.close()
                
        result = await asyncio.to_thread(_save_section)
        
        # Mettre à jour l'index de recherche
        if result:
            try:
                await self._index_section_content(section)
                logger.info(f"Index de section {section['id']} mis à jour")
            except Exception as e:
                logger.error(f"Erreur lors de la mise à jour de l'index de section: {str(e)}")
        
        return result

    async def search_relevant_sections(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Recherche des sections pertinentes pour une requête.
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des sections pertinentes
        """
        try:
            # Générer l'embedding pour la requête
            embedding = await self.llm_orchestrator.get_embeddings(query)
            
            # Rechercher dans la collection
            results = self.sections_collection.query(
                query_embeddings=[embedding],
                n_results=limit * 3  # Récupérer plus pour filtrer les doublons
            )
            
            if not results or not results['ids'][0]:
                return []
            
            # Extraire les IDs des sections en supprimant les suffixes de chunks
            section_ids_with_chunks = results['ids'][0]
            section_ids = set()
            
            for id_with_chunk in section_ids_with_chunks:
                section_id = id_with_chunk.split('_')[0]
                section_ids.add(section_id)
            
            # Limiter au nombre demandé
            section_ids = list(section_ids)[:limit]
            
            # Récupérer les détails complets des sections
            sections = []
            for section_id in section_ids:
                try:
                    section = await self.get_section(int(section_id))
                    
                    # Ajouter un aperçu du contenu
                    full_content = section.get('content', '')
                    section['content_preview'] = full_content[:300] + "..." if len(full_content) > 300 else full_content
                    
                    sections.append(section)
                except ValueError:
                    # La section a peut-être été supprimée
                    continue
            
            return sections
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de sections: {str(e)}")
            # En cas d'erreur, retourner une liste vide
            return []

    async def _index_section_content(self, section: Dict[str, Any]) -> bool:
        """
        Indexe le contenu d'une section dans ChromaDB pour la recherche.
        
        Args:
            section: Dictionnaire de la section à indexer
            
        Returns:
            True si l'opération a réussi
        """
        section_id = section['id']
        content = section.get('content', '')
        title = section.get('titre', '')
        
        # Si pas de contenu, supprimer les index existants
        if not content:
            try:
                self.sections_collection.delete(where={"section_id": section_id})
                return True
            except Exception as e:
                logger.error(f"Erreur lors de la suppression des chunks pour la section {section_id}: {str(e)}")
                return False
        
        # Découper le contenu en chunks
        chunks = self.text_splitter.split_text(content)
        
        if not chunks:
            return True  # Rien à indexer
        
        try:
            # Supprimer les chunks existants
            self.sections_collection.delete(where={"section_id": section_id})
            
            # Créer de nouveaux chunks
            ids = [f"{section_id}_{i}" for i in range(len(chunks))]
            metadata = []
            
            for i, chunk in enumerate(chunks):
                # Déterminer le type de contenu pour chaque chunk
                chunk_type = self.text_splitter._determine_content_type(chunk)
                
                # Extraire des mots-clés pour améliorer la recherche
                keywords = self._extract_keywords(chunk)
                
                metadata.append({
                    "section_id": section_id,
                    "title": title,
                    "chunk_index": i,
                    "chunk_type": chunk_type,
                    "keywords": ",".join(keywords[:10]),  # Limiter à 10 mots-clés
                    "chunk_size": len(chunk),
                    "timestamp": datetime.now().isoformat()
                })
            
            # Ajouter les chunks à la collection
            self.sections_collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadata
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la section {section_id}: {str(e)}")
            return False

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extrait les mots-clés significatifs d'un texte.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Liste des mots-clés
        """
        # Nettoyer le texte
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        
        # Filtrer les mots vides
        stopwords = {"le", "la", "les", "un", "une", "des", "et", "ou", "a", "à", "de", "du", "en", 
                     "est", "ce", "que", "qui", "dans", "par", "pour", "sur", "avec", "sans", 
                     "il", "elle", "ils", "elles", "nous", "vous", "je", "tu"}
        
        keywords = [word for word in words if word not in stopwords and len(word) > 3]
        
        # Compter les occurrences
        keyword_counts = {}
        for word in keywords:
            keyword_counts[word] = keyword_counts.get(word, 0) + 1
        
        # Trier par fréquence
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [word for word, count in sorted_keywords]

    # --- MÉTHODES POUR L'ÉVALUATION DES COMPÉTENCES ---

    async def analyze_competences_from_journal(self) -> Dict[str, Any]:
        """
        Analyse les entrées du journal pour identifier les compétences développées.
        
        Returns:
            Dictionnaire avec les résultats de l'analyse
        """
        def _analyze_competences():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Récupérer toutes les entrées du journal
                cursor.execute('''
                SELECT id, date, texte as content, type_entree
                FROM journal_entries
                ORDER BY date DESC
                ''')
                
                entries = [dict(row) for row in cursor.fetchall()]
                
                # Définir les mots-clés associés à chaque compétence RNCP
                competence_keywords = {
                    "analyse_besoins": [
                        "analyse", "besoin", "exigence", "requirement", "interview", "utilisateur",
                        "client", "stakeholder", "partie prenante", "évaluation", "diagnostic"
                    ],
                    "conception_systemes": [
                        "conception", "architecture", "design", "modélisation", "UML", "diagramme",
                        "système", "database", "base de données", "API", "microservice", "solution"
                    ],
                    "gestion_projets": [
                        "projet", "planning", "délai", "deadline", "budget", "ressource", "équipe",
                        "coordination", "gestion", "management", "agile", "scrum", "sprint", "kanban"
                    ],
                    "maintenance_evolution": [
                        "maintenance", "évolution", "mise à jour", "update", "correction", "bug",
                        "optimisation", "performance", "refactoring", "legacy", "dette technique"
                    ],
                    "assistance_formation": [
                        "formation", "assistance", "support", "aide", "utilisateur", "documentation",
                        "tutoriel", "guide", "présentation", "démonstration", "atelier", "workshop"
                    ]
                }
                
                # Initialiser les compteurs
                competence_counts = {key: 0 for key in competence_keywords.keys()}
                competence_entries = {key: [] for key in competence_keywords.keys()}
                
                # Analyser chaque entrée
                for entry in entries:
                    content = entry.get("content", "").lower()
                    entry_competences = set()
                    
                    # Vérifier les mots-clés pour chaque compétence
                    for competence, keywords in competence_keywords.items():
                        matched_keywords = [keyword for keyword in keywords if keyword in content]
                        
                        if matched_keywords:
                            competence_counts[competence] += 1
                            entry_competences.add(competence)
                            competence_entries[competence].append({
                                "entry_id": entry["id"],
                                "date": entry["date"],
                                "matched_keywords": matched_keywords
                            })
                    
                    # Mettre à jour la table de liaison (à implémenter si nécessaire)
                
                # Récupérer ou créer le portfolio
                portfolio_path = os.path.join("data", "portfolio_competences.json")
                if os.path.exists(portfolio_path):
                    with open(portfolio_path, "r") as f:
                        portfolio = json.load(f)
                else:
                    portfolio = {
                        "competences": {key: [] for key in competence_keywords.keys()},
                        "date_evaluation": datetime.now().strftime("%Y-%m-%d"),
                        "commentaire_general": ""
                    }
                
                # Mettre à jour les statistiques
                portfolio["statistiques"] = {
                    "mentions_par_competence": competence_counts,
                    "nombre_entrees_total": len(entries),
                    "derniere_analyse": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Sauvegarder le portfolio
                with open(portfolio_path, "w") as f:
                    json.dump(portfolio, f, indent=2)
                
                return {
                    "competence_counts": competence_counts,
                    "entry_count": len(entries),
                    "competence_entries": competence_entries
                }
                
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse des compétences: {str(e)}")
                raise
            finally:
                conn.close()
                
        return await asyncio.to_thread(_analyze_competences)

    async def initialize_rncp_structure(self) -> bool:
        """
        Initialise la structure du mémoire selon les exigences RNCP.
        
        Returns:
            True si l'initialisation a réussi
        """
        def _init_structure():
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                
                # Vérifier si des sections existent déjà
                cursor.execute("SELECT COUNT(*) FROM memoire_sections")
                if cursor.fetchone()[0] > 0:
                    # Structure déjà initialisée
                    return True
                
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Définir la structure selon les exigences RNCP
                sections = [
                    # Section 1: Introduction
                    (1, "Introduction", "", 1, None, now),
                    (2, "Présentation de l'entreprise", "", 2, 1, now),
                    (3, "Secteur d'activité", "", 3, 1, now),
                    (4, "Contexte de la mission", "", 4, 1, now),
                    (5, "Objectifs du mémoire", "", 5, 1, now),
                    
                    # Section 2: Description de la mission
                    (6, "Description de la mission", "", 6, None, now),
                    (7, "Fiche de poste", "", 7, 6, now),
                    (8, "Tâches réalisées", "", 8, 6, now),
                    (9, "Responsabilités assumées", "", 9, 6, now),
                    (10, "Projets", "", 10, 6, now),
                    (11, "Position et rôle dans l'équipe", "", 11, 6, now),
                    
                    # Section 3: Analyse des compétences
                    (12, "Analyse des compétences", "", 12, None, now),
                    (13, "Compétences clés développées", "", 13, 12, now),
                    (14, "Lien avec le titre RNCP", "", 14, 12, now),
                    (15, "Application des connaissances acquises", "", 15, 12, now),
                    
                    # Section 4: Évaluation de la performance
                    (16, "Évaluation de la performance", "", 16, None, now),
                    (17, "Analyse de performance", "", 17, 16, now),
                    (18, "Auto-évaluation critique", "", 18, 16, now),
                    
                    # Section 5: Réflexion personnelle et professionnelle
                    (19, "Réflexion personnelle et professionnelle", "", 19, None, now),
                    (20, "Intégration dans l'entreprise", "", 20, 19, now),
                    (21, "Impact du travail réalisé", "", 21, 19, now),
                    (22, "Évolution personnelle", "", 22, 19, now),
                    (23, "Domaines d'amélioration", "", 23, 19, now),
                    
                    # Section 6: Conclusion
                    (24, "Conclusion", "", 24, None, now),
                    (25, "Synthèse des apprentissages", "", 25, 24, now),
                    (26, "Implications pour la carrière future", "", 26, 24, now),
                    
                    # Section 7: Annexes
                    (27, "Annexes", "", 27, None, now),
                ]
                
                # Insérer les sections
                cursor.executemany('''
                INSERT INTO memoire_sections (id, titre, content, ordre, parent_id, derniere_modification)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', sections)
                
                conn.commit()
                return True
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Erreur lors de l'initialisation de la structure RNCP: {str(e)}")
                return False
            finally:
                conn.close()
                
        return await asyncio.to_thread(_init_structure)