import sqlite3
import json
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging

from db.database import get_db_connection, get_sections_collection
from core.exceptions import DatabaseError
from services.llm_service import get_embeddings
from utils.text_processing import AdaptiveTextSplitter

logger = logging.getLogger(__name__)

class MemoireRepository:
    """Couche d'accès aux données pour les sections du mémoire"""
    
    @staticmethod
    async def add_section(section_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute une section au mémoire
        
        Args:
            section_data: Données de la section à ajouter
            
        Returns:
            Dict: La section ajoutée avec son ID et autres métadonnées
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Insertion de la section
            cursor.execute('''
            INSERT INTO memoire_sections (
                titre, 
                contenu, 
                ordre, 
                parent_id, 
                derniere_modification
            ) VALUES (?, ?, ?, ?, ?)
            ''', (
                section_data["titre"], 
                section_data.get("contenu"), 
                section_data["ordre"], 
                section_data.get("parent_id"), 
                now
            ))
            
            section_id = cursor.lastrowid
            conn.commit()
            
            # Indexer le contenu si présent
            if section_data.get("contenu"):
                await MemoireRepository._index_section_content(
                    section_id, 
                    section_data["titre"],
                    section_data["contenu"]
                )
            
            # Récupérer la section complète
            return await MemoireRepository.get_section(section_id)
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de l'ajout d'une section: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de l'ajout d'une section: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de l'ajout d'une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de l'ajout d'une section: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_section(section_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une section spécifique par son ID
        
        Args:
            section_id: ID de la section à récupérer
            
        Returns:
            Dict: La section complète ou None si introuvable
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Récupérer la section
            cursor.execute('''
            SELECT id, titre, contenu, ordre, parent_id, derniere_modification
            FROM memoire_sections
            WHERE id = ?
            ''', (section_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            section = dict(row)
            
            # Récupérer le titre du parent si présent
            if section['parent_id']:
                cursor.execute('''
                SELECT titre FROM memoire_sections WHERE id = ?
                ''', (section['parent_id'],))
                parent = cursor.fetchone()
                if parent:
                    section['parent_titre'] = parent['titre']
            
            # Récupérer les entrées de journal associées
            cursor.execute('''
            SELECT j.id, j.date, j.texte as content, j.type_entree
            FROM journal_entries j
            JOIN section_entries se ON j.id = se.entry_id
            WHERE se.section_id = ?
            ''', (section_id,))
            
            section['journal_entries'] = [dict(row) for row in cursor.fetchall()]
            
            # Récupérer les enfants directs
            cursor.execute('''
            SELECT id, titre, contenu, ordre, parent_id, derniere_modification
            FROM memoire_sections
            WHERE parent_id = ?
            ORDER BY ordre
            ''', (section_id,))
            
            section['children'] = [dict(row) for row in cursor.fetchall()]
            
            return section
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération d'une section: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération d'une section: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération d'une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération d'une section: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_sections(parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Récupère les sections du mémoire
        
        Args:
            parent_id: ID du parent (None pour les sections racines)
            
        Returns:
            List[Dict]: Liste des sections correspondantes
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            if parent_id is not None:
                cursor.execute('''
                SELECT id, titre, contenu, ordre, parent_id, derniere_modification
                FROM memoire_sections
                WHERE parent_id = ?
                ORDER BY ordre
                ''', (parent_id,))
            else:
                cursor.execute('''
                SELECT id, titre, contenu, ordre, parent_id, derniere_modification
                FROM memoire_sections
                WHERE parent_id IS NULL
                ORDER BY ordre
                ''')
            
            sections = [dict(row) for row in cursor.fetchall()]
            
            # Pour chaque section, récupérer le nombre d'enfants
            for section in sections:
                cursor.execute('''
                SELECT COUNT(*) 
                FROM memoire_sections 
                WHERE parent_id = ?
                ''', (section['id'],))
                section['children_count'] = cursor.fetchone()[0]
                
                # Ajouter un aperçu du contenu
                if section.get('contenu'):
                    content_preview = section['contenu'][:300] + "..." if len(section['contenu']) > 300 else section['contenu']
                    section['content_preview'] = content_preview
            
            return sections
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des sections: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération des sections: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des sections: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des sections: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def update_section(section_id: int, section_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Met à jour une section existante
        
        Args:
            section_id: ID de la section à mettre à jour
            section_data: Nouvelles données de la section
            
        Returns:
            Dict: La section mise à jour ou None si introuvable
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Vérifier si la section existe
            cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
            if not cursor.fetchone():
                return None
            
            # Récupérer les valeurs actuelles
            cursor.execute('''
            SELECT titre, contenu, ordre, parent_id
            FROM memoire_sections
            WHERE id = ?
            ''', (section_id,))
            current = dict(cursor.fetchone())
            
            # Préparer les valeurs à mettre à jour
            titre = section_data.get("titre", current["titre"])
            contenu = section_data.get("contenu", current["contenu"])
            ordre = section_data.get("ordre", current["ordre"])
            parent_id = section_data.get("parent_id", current["parent_id"])
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Mise à jour de la section
            cursor.execute('''
            UPDATE memoire_sections 
            SET titre = ?, contenu = ?, ordre = ?, parent_id = ?, derniere_modification = ?
            WHERE id = ?
            ''', (titre, contenu, ordre, parent_id, now, section_id))
            
            conn.commit()
            
            # Mettre à jour l'index vectoriel si le contenu a changé
            if "contenu" in section_data and section_data["contenu"] != current["contenu"]:
                await MemoireRepository._index_section_content(
                    section_id, 
                    titre,
                    contenu
                )
            
            # Récupérer la section mise à jour
            return await MemoireRepository.get_section(section_id)
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la mise à jour d'une section: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la mise à jour d'une section: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la mise à jour d'une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de la mise à jour d'une section: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def delete_section(section_id: int) -> bool:
        """
        Supprime une section du mémoire
        
        Args:
            section_id: ID de la section à supprimer
            
        Returns:
            bool: True si la section a été supprimée, False si introuvable
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Vérifier si la section existe
            cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
            if not cursor.fetchone():
                return False
            
            # Vérifier s'il y a des sections enfants
            cursor.execute("SELECT COUNT(*) FROM memoire_sections WHERE parent_id = ?", (section_id,))
            children_count = cursor.fetchone()[0]
            
            if children_count > 0:
                # Option 1: Erreur si des enfants existent
                # raise DatabaseError(f"Impossible de supprimer la section {section_id}, elle contient {children_count} sections enfants.")
                
                # Option 2: Supprimer également les enfants (récursif)
                cursor.execute("SELECT id FROM memoire_sections WHERE parent_id = ?", (section_id,))
                child_ids = [row[0] for row in cursor.fetchall()]
                
                for child_id in child_ids:
                    # Appel récursif pour supprimer chaque enfant
                    # Pour éviter les appels asynchrones dans une transaction, on utilise une fonction interne
                    cursor.execute("DELETE FROM section_entries WHERE section_id = ?", (child_id,))
                    cursor.execute("DELETE FROM memoire_sections WHERE id = ?", (child_id,))
                    
                    # Supprimer de l'index vectoriel
                    try:
                        sections_collection = get_sections_collection()
                        sections_collection.delete(where={"section_id": str(child_id)})
                    except Exception as e:
                        logger.warning(f"Erreur lors de la suppression de la section {child_id} dans ChromaDB: {str(e)}")
            
            # Supprimer les associations avec les entrées de journal
            cursor.execute("DELETE FROM section_entries WHERE section_id = ?", (section_id,))
            
            # Supprimer la section
            cursor.execute("DELETE FROM memoire_sections WHERE id = ?", (section_id,))
            
            # Supprimer de l'index vectoriel
            try:
                sections_collection = get_sections_collection()
                sections_collection.delete(where={"section_id": str(section_id)})
            except Exception as e:
                logger.warning(f"Erreur lors de la suppression de la section dans ChromaDB: {str(e)}")
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la suppression d'une section: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la suppression d'une section: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la suppression d'une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression d'une section: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_outline() -> List[Dict[str, Any]]:
        """
        Récupère la structure complète du plan du mémoire
        
        Returns:
            List[Dict]: Structure hiérarchique des sections
        """
        # Récupérer toutes les sections
        all_sections = await MemoireRepository.get_all_sections()
        
        # Créer un dictionnaire pour un accès rapide par ID
        sections_dict = {section["id"]: section for section in all_sections}
        
        # Identifier les sections racines (sans parent)
        root_sections = [section for section in all_sections if section["parent_id"] is None]
        
        # Trier par ordre
        root_sections.sort(key=lambda x: x["ordre"])
        
        # Fonction récursive pour construire la hiérarchie
        def build_tree(parent_id=None):
            children = [s for s in all_sections if s["parent_id"] == parent_id]
            children.sort(key=lambda x: x["ordre"])
            
            result = []
            for child in children:
                # Ajouter un niveau de hiérarchie
                level = 0
                current_parent = child.get("parent_id")
                while current_parent is not None:
                    level += 1
                    parent_data = sections_dict.get(current_parent)
                    if not parent_data:
                        break
                    current_parent = parent_data.get("parent_id")
                
                child_section = {
                    "id": child["id"],
                    "titre": child["titre"],
                    "ordre": child["ordre"],
                    "children": build_tree(child["id"]),
                    "has_content": bool(child.get("contenu")),
                    "level": level
                }
                result.append(child_section)
            return result
        
        # Construire le plan
        outline = build_tree(None)
        
        # Calculer des statistiques pour le plan
        total_sections = len(all_sections)
        with_content = sum(1 for s in all_sections if s.get("contenu"))
        progress = round(with_content / max(total_sections, 1) * 100, 2)
        
        # Ajouter les statistiques au résultat
        outline_with_stats = {
            "sections": outline,
            "total_sections": total_sections,
            "total_with_content": with_content,
            "progress": progress
        }
        
        return outline_with_stats
    
    @staticmethod
    async def get_all_sections() -> List[Dict[str, Any]]:
        """
        Récupère toutes les sections du mémoire
        
        Returns:
            List[Dict]: Liste de toutes les sections
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, titre, contenu, ordre, parent_id, derniere_modification
            FROM memoire_sections
            ORDER BY ordre
            ''')
            
            sections = [dict(row) for row in cursor.fetchall()]
            return sections
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération de toutes les sections: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération de toutes les sections: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de toutes les sections: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération de toutes les sections: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def search_sections(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche des sections par similarité sémantique
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            List[Dict]: Liste des sections les plus pertinentes
        """
        try:
            # Obtenir l'embedding de la requête
            embedding = await get_embeddings(query)
            
            # Rechercher dans ChromaDB
            sections_collection = get_sections_collection()
            results = sections_collection.query(
                query_embeddings=[embedding],
                n_results=limit * 2  # Récupérer plus de résultats pour gérer les doublons
            )
            
            if not results or not results['ids'][0]:
                return []
            
            # Extraire les IDs de section des IDs de chunk
            section_ids = set()
            for id in results['ids'][0]:
                # Format: section_id_chunk_index
                parts = id.split('_')
                if len(parts) >= 2:
                    try:
                        section_ids.add(int(parts[0]))
                    except ValueError:
                        continue
            
            # Limiter le nombre de sections
            section_ids = list(section_ids)[:limit]
            
            # Récupérer les sections complètes
            sections = []
            for section_id in section_ids:
                section = await MemoireRepository.get_section(section_id)
                if section:
                    # Ajouter un extrait du contenu
                    if section.get("contenu"):
                        content_preview = section["contenu"][:300] + "..." if len(section["contenu"]) > 300 else section["contenu"]
                        section["content_preview"] = content_preview
                    sections.append(section)
            
            return sections
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de sections: {str(e)}")
            # Fallback sur une recherche par mots-clés
            return await MemoireRepository._fallback_section_search(query, limit)
    
    @staticmethod
    async def _fallback_section_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche de sections par mots-clés (fallback si la recherche vectorielle échoue)
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            List[Dict]: Liste des sections les plus pertinentes
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Extraire les mots-clés de la requête
            keywords = [kw.strip() for kw in query.lower().split() if len(kw.strip()) > 2]
            if not keywords:
                return []
            
            # Construire une requête LIKE pour chaque mot-clé
            like_clauses = []
            params = []
            
            for keyword in keywords:
                like_clauses.append("(titre LIKE ? OR contenu LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            
            # Construire la requête complète
            query = f'''
            SELECT id, titre, contenu, ordre, parent_id, derniere_modification,
                ({"+" * len(like_clauses)*2}) as match_count
            FROM memoire_sections
            WHERE {" OR ".join(like_clauses)}
            ORDER BY match_count DESC
            LIMIT ?
            '''
            
            # Remplacer les + par "CASE WHEN clause THEN 1 ELSE 0 END"
            match_cases = []
            for i in range(len(keywords)):
                match_cases.append(f"CASE WHEN titre LIKE ? THEN 2 ELSE 0 END")
                match_cases.append(f"CASE WHEN contenu LIKE ? THEN 1 ELSE 0 END")
            
            query = query.replace("+", " + ".join(match_cases))
            
            params.append(limit)
            
            # Exécuter la recherche
            cursor.execute(query, params)
            sections = [dict(row) for row in cursor.fetchall()]
            
            # Ajouter un aperçu du contenu pour chaque section
            for section in sections:
                # Supprimer le champ match_count
                if 'match_count' in section:
                    del section['match_count']
                
                # Ajouter un aperçu du contenu
                if section.get('contenu'):
                    content_preview = section['contenu'][:300] + "..." if len(section['contenu']) > 300 else section['contenu']
                    section['content_preview'] = content_preview
            
            return sections
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la recherche par mots-clés: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par mots-clés: {str(e)}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    async def link_entry_to_section(section_id: int, entry_id: int) -> bool:
        """
        Lie une entrée de journal à une section
        
        Args:
            section_id: ID de la section
            entry_id: ID de l'entrée de journal
            
        Returns:
            bool: True si l'opération a réussi
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Vérifier si la section existe
            cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
            if not cursor.fetchone():
                return False
            
            # Vérifier si l'entrée existe
            cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
            if not cursor.fetchone():
                return False
            
            # Vérifier si l'association existe déjà
            cursor.execute('''
            SELECT 1 FROM section_entries 
            WHERE section_id = ? AND entry_id = ?
            ''', (section_id, entry_id))
            
            if cursor.fetchone():
                # L'association existe déjà
                return True
            
            # Créer l'association
            cursor.execute('''
            INSERT INTO section_entries (section_id, entry_id)
            VALUES (?, ?)
            ''', (section_id, entry_id))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de l'association d'une entrée à une section: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de l'association d'une entrée à une section: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de l'association d'une entrée à une section: {str(e)}")
            raise DatabaseError(f"Erreur lors de l'association d'une entrée à une section: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def unlink_entry_from_section(section_id: int, entry_id: int) -> bool:
        """
        Supprime l'association entre une entrée de journal et une section
        
        Args:
            section_id: ID de la section
            entry_id: ID de l'entrée de journal
            
        Returns:
            bool: True si l'opération a réussi
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Supprimer l'association
            cursor.execute('''
            DELETE FROM section_entries
            WHERE section_id = ? AND entry_id = ?
            ''', (section_id, entry_id))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la suppression de l'association: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la suppression de l'association: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la suppression de l'association: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression de l'association: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_bibliographie() -> List[Dict[str, Any]]:
        """
        Récupère toutes les références bibliographiques
        
        Returns:
            List[Dict]: Liste des références bibliographiques
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Vérifier si la table existe
            cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='bibliography_references'
            ''')
            
            if not cursor.fetchone():
                # La table n'existe pas encore
                return []
            
            cursor.execute('''
            SELECT id, type, title, authors, year, publisher, journal, volume, issue, 
                   pages, url, doi, accessed_date, notes, last_modified
            FROM bibliography_references
            ORDER BY authors, year
            ''')
            
            references = []
            for row in cursor.fetchall():
                reference = dict(row)
                
                # Convertir les auteurs de JSON si nécessaire
                if isinstance(reference.get("authors"), str):
                    try:
                        reference["authors"] = json.loads(reference["authors"])
                    except json.JSONDecodeError:
                        # Si le décodage échoue, garder comme chaîne
                        pass
                
                # Générer une citation formatée
                authors = reference.get("authors", "")
                if isinstance(authors, list):
                    if len(authors) > 3:
                        author_text = f"{authors[0]} et al."
                    else:
                        author_text = ", ".join(authors)
                else:
                    author_text = str(authors)
                
                year = reference.get("year", "")
                title = reference.get("title", "")
                publisher = reference.get("publisher", "")
                
                citation = f"{author_text} ({year}). {title}."
                if publisher:
                    citation += f" {publisher}."
                
                reference["citation"] = citation
                references.append(reference)
            
            return references
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des références: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération des références: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des références: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des références: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def add_bibliographie_reference(reference_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute une référence bibliographique
        
        Args:
            reference_data: Données de la référence à ajouter
            
        Returns:
            Dict: La référence ajoutée avec son ID
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Créer la table si elle n'existe pas
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bibliography_references (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                authors TEXT NOT NULL,
                year INTEGER,
                publisher TEXT,
                journal TEXT,
                volume TEXT,
                issue TEXT,
                pages TEXT,
                url TEXT,
                doi TEXT,
                accessed_date TEXT,
                notes TEXT,
                last_modified TEXT NOT NULL
            )
            ''')
            
            # Génération d'un ID unique
            reference_id = str(uuid.uuid4())
            
            # Préparation des auteurs (conversion en JSON si c'est une liste)
            authors = reference_data.get("authors", "")
            if isinstance(authors, list):
                authors = json.dumps(authors)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Insertion de la référence
            cursor.execute('''
            INSERT INTO bibliography_references (
                id, type, title, authors, year, publisher, journal, volume, 
                issue, pages, url, doi, accessed_date, notes, last_modified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reference_id,
                reference_data.get("type", ""),
                reference_data.get("title", ""),
                authors,
                reference_data.get("year"),
                reference_data.get("publisher"),
                reference_data.get("journal"),
                reference_data.get("volume"),
                reference_data.get("issue"),
                reference_data.get("pages"),
                reference_data.get("url"),
                reference_data.get("doi"),
                reference_data.get("accessed_date"),
                reference_data.get("notes"),
                now
            ))
            
            conn.commit()
            
            # Récupération de la référence complète
            cursor.execute('''
            SELECT id, type, title, authors, year, publisher, journal, volume, issue, 
                   pages, url, doi, accessed_date, notes, last_modified
            FROM bibliography_references
            WHERE id = ?
            ''', (reference_id,))
            
            reference = dict(cursor.fetchone())
            
            # Convertir les auteurs de JSON si nécessaire
            if isinstance(reference.get("authors"), str):
                try:
                    reference["authors"] = json.loads(reference["authors"])
                except json.JSONDecodeError:
                    # Si le décodage échoue, garder comme chaîne
                    pass
            
            # Générer une citation formatée
            authors = reference.get("authors", "")
            if isinstance(authors, list):
                if len(authors) > 3:
                    author_text = f"{authors[0]} et al."
                else:
                    author_text = ", ".join(authors)
            else:
                author_text = str(authors)
            
            year = reference.get("year", "")
            title = reference.get("title", "")
            publisher = reference.get("publisher", "")
            
            citation = f"{author_text} ({year}). {title}."
            if publisher:
                citation += f" {publisher}."
            
            reference["citation"] = citation
            
            return reference
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de l'ajout d'une référence: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de l'ajout d'une référence: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de l'ajout d'une référence: {str(e)}")
            raise DatabaseError(f"Erreur lors de l'ajout d'une référence: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def _index_section_content(section_id: int, title: str, content: str) -> None:
        """
        Indexe le contenu d'une section dans ChromaDB pour la recherche sémantique
        
        Args:
            section_id: ID de la section
            title: Titre de la section
            content: Contenu à indexer
        """
        # Splitter le contenu en chunks
        splitter = AdaptiveTextSplitter()
        chunks = splitter.split_text(content)
        
        if not chunks:
            return
        
        # Obtenir la collection
        sections_collection = get_sections_collection()
        
        # Supprimer les chunks existants pour cette section
        try:
            sections_collection.delete(where={"section_id": str(section_id)})
        except Exception as e:
            logger.warning(f"Erreur lors de la suppression des chunks existants: {str(e)}")
        
        # Préparer les données pour l'indexation
        ids = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            ids.append(f"{section_id}_{i}")
            chunk_type = splitter._determine_content_type(chunk)
            
            metadatas.append({
                "section_id": str(section_id),
                "title": title,
                "chunk_index": i,
                "chunk_type": chunk_type,
                "chunk_size": len(chunk),
                "timestamp": datetime.now().isoformat()
            })
        
        # Indexer les chunks
        try:
            sections_collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadatas
            )
            
            logger.info(f"Indexé {len(chunks)} chunks pour la section {section_id}")
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation du contenu de la section: {str(e)}")