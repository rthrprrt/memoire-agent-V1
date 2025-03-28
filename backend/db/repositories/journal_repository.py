import sqlite3
import json
import asyncio
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging

from db.database import get_db_connection, get_journal_collection
from core.exceptions import DatabaseError
from utils.text_processing import extract_automatic_tags

logger = logging.getLogger(__name__)

class JournalRepository:
    """Couche d'accès aux données pour les entrées de journal"""
    
    @staticmethod
    async def add_entry(entry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute une entrée de journal dans la base de données
        
        Args:
            entry_data: Données de l'entrée à ajouter
            
        Returns:
            Dict: L'entrée ajoutée avec son ID et autres métadonnées
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            entreprise_id = entry_data.get("entreprise_id")
            
            # Déterminer l'entreprise_id si non fourni
            if entreprise_id is None:
                cursor.execute('''
                SELECT id FROM entreprises 
                WHERE date_debut <= ? AND (date_fin IS NULL OR date_fin >= ?)
                ''', (entry_data["date"], entry_data["date"]))
                result = cursor.fetchone()
                if result:
                    entreprise_id = result[0]
            
            # Générer des tags automatiquement si non fournis
            tags = entry_data.get("tags")
            if not tags:
                tags = extract_automatic_tags(entry_data["texte"])
            
            # Insertion de l'entrée
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
            INSERT INTO journal_entries (
                date, 
                texte, 
                entreprise_id, 
                type_entree, 
                source_document, 
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                entry_data["date"], 
                entry_data["texte"], 
                entreprise_id, 
                entry_data.get("type_entree", "quotidien"), 
                entry_data.get("source_document"), 
                now
            ))
            
            entry_id = cursor.lastrowid
            
            # Ajouter les tags
            if tags:
                for tag in tags:
                    # Ignorer les tags vides
                    if not tag or len(tag.strip()) == 0:
                        continue
                    
                    # Récupérer ou créer le tag
                    cursor.execute("SELECT id FROM tags WHERE nom = ?", (tag,))
                    result = cursor.fetchone()
                    
                    if result:
                        tag_id = result[0]
                    else:
                        cursor.execute("INSERT INTO tags (nom) VALUES (?)", (tag,))
                        tag_id = cursor.lastrowid
                    
                    # Associer le tag à l'entrée
                    try:
                        cursor.execute(
                            "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", 
                            (entry_id, tag_id)
                        )
                    except sqlite3.IntegrityError:
                        # Ignorer si l'association existe déjà
                        pass
            
            # Indexer dans ChromaDB
            journal_collection = get_journal_collection()
            try:
                journal_collection.add(
                    documents=[entry_data["texte"]],
                    metadatas=[{
                        "date": entry_data["date"], 
                        "entry_id": entry_id,
                        "type": entry_data.get("type_entree", "quotidien"),
                        "tags": ",".join(tags) if tags else ""
                    }],
                    ids=[f"entry_{entry_id}"]
                )
            except Exception as e:
                logger.error(f"Erreur lors de l'indexation dans ChromaDB: {str(e)}")
                # Ne pas annuler la transaction pour cette erreur
            
            conn.commit()
            
            # Récupérer l'entrée complète
            return await JournalRepository.get_entry(entry_id)
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de l'ajout d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de l'ajout d'une entrée: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de l'ajout d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur lors de l'ajout d'une entrée: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_entry(entry_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère une entrée spécifique par son ID
        
        Args:
            entry_id: ID de l'entrée à récupérer
            
        Returns:
            Dict: L'entrée complète ou None si introuvable
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Récupérer l'entrée avec le nom de l'entreprise
            cursor.execute('''
            SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, 
                j.entreprise_id, j.created_at, e.nom as entreprise_nom
            FROM journal_entries j
            LEFT JOIN entreprises e ON j.entreprise_id = e.id
            WHERE j.id = ?
            ''', (entry_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            entry = dict(row)
            
            # Récupérer les tags associés
            cursor.execute('''
            SELECT t.nom FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id = ?
            ''', (entry_id,))
            
            entry['tags'] = [row[0] for row in cursor.fetchall()]
            
            return entry
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération d'une entrée: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération d'une entrée: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def update_entry(entry_id: int, entry_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Met à jour une entrée existante
        
        Args:
            entry_id: ID de l'entrée à mettre à jour
            entry_data: Nouvelles données de l'entrée
            
        Returns:
            Dict: L'entrée mise à jour ou None si introuvable
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Vérifier si l'entrée existe
            cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
            if not cursor.fetchone():
                return None
            
            # Récupérer les valeurs actuelles
            cursor.execute('''
            SELECT date, texte, entreprise_id, type_entree, source_document
            FROM journal_entries
            WHERE id = ?
            ''', (entry_id,))
            current = dict(cursor.fetchone())
            
            # Préparer les valeurs à mettre à jour
            date = entry_data.get("date", current["date"])
            texte = entry_data.get("texte", current["texte"])
            entreprise_id = entry_data.get("entreprise_id", current["entreprise_id"])
            type_entree = entry_data.get("type_entree", current["type_entree"])
            source_document = entry_data.get("source_document", current["source_document"])
            
            # Mise à jour de l'entrée
            cursor.execute('''
            UPDATE journal_entries 
            SET date = ?, texte = ?, entreprise_id = ?, type_entree = ?, source_document = ?
            WHERE id = ?
            ''', (date, texte, entreprise_id, type_entree, source_document, entry_id))
            
            # Mettre à jour les tags si fournis
            if "tags" in entry_data:
                # Supprimer les anciens tags
                cursor.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
                
                # Ajouter les nouveaux tags
                tags = entry_data["tags"]
                if tags:
                    for tag in tags:
                        # Ignorer les tags vides
                        if not tag or len(tag.strip()) == 0:
                            continue
                        
                        # Récupérer ou créer le tag
                        cursor.execute("SELECT id FROM tags WHERE nom = ?", (tag,))
                        result = cursor.fetchone()
                        
                        if result:
                            tag_id = result[0]
                        else:
                            cursor.execute("INSERT INTO tags (nom) VALUES (?)", (tag,))
                            tag_id = cursor.lastrowid
                        
                        # Associer le tag à l'entrée
                        cursor.execute(
                            "INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", 
                            (entry_id, tag_id)
                        )
            
            # Mettre à jour dans ChromaDB si le texte a changé
            if texte != current["texte"]:
                journal_collection = get_journal_collection()
                try:
                    # Récupérer les tags actuels pour les métadonnées
                    cursor.execute('''
                    SELECT t.nom FROM tags t
                    JOIN entry_tags et ON t.id = et.tag_id
                    WHERE et.entry_id = ?
                    ''', (entry_id,))
                    tags = [row[0] for row in cursor.fetchall()]
                    
                    journal_collection.update(
                        documents=[texte],
                        metadatas=[{
                            "date": date, 
                            "entry_id": entry_id,
                            "type": type_entree,
                            "tags": ",".join(tags) if tags else ""
                        }],
                        ids=[f"entry_{entry_id}"]
                    )
                except Exception as e:
                    logger.error(f"Erreur lors de la mise à jour dans ChromaDB: {str(e)}")
                    # Ne pas annuler la transaction pour cette erreur
            
            conn.commit()
            
            # Récupérer l'entrée mise à jour
            return await JournalRepository.get_entry(entry_id)
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la mise à jour d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la mise à jour d'une entrée: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la mise à jour d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur lors de la mise à jour d'une entrée: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def delete_entry(entry_id: int) -> bool:
        """
        Supprime une entrée de journal
        
        Args:
            entry_id: ID de l'entrée à supprimer
            
        Returns:
            bool: True si l'entrée a été supprimée, False si introuvable
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Vérifier si l'entrée existe
            cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
            if not cursor.fetchone():
                return False
            
            # Supprimer l'entrée (les tags associés seront supprimés par CASCADE)
            cursor.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
            
            # Supprimer de ChromaDB
            journal_collection = get_journal_collection()
            try:
                journal_collection.delete(ids=[f"entry_{entry_id}"])
            except Exception as e:
                logger.error(f"Erreur lors de la suppression dans ChromaDB: {str(e)}")
                # Ne pas annuler la transaction pour cette erreur
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la suppression d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la suppression d'une entrée: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la suppression d'une entrée: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression d'une entrée: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_entries(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        entreprise_id: Optional[int] = None,
        type_entree: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Récupère les entrées de journal avec filtres optionnels
        
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
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            query = '''
            SELECT DISTINCT j.id, j.date, j.texte as content, j.type_entree, j.source_document, 
                j.entreprise_id, e.nom as entreprise_nom
            FROM journal_entries j
            LEFT JOIN entreprises e ON j.entreprise_id = e.id
            '''
            
            params = []
            conditions = []
            
            # Ajouter la jointure avec les tags si tag est spécifié
            if tag:
                query += '''
                LEFT JOIN entry_tags et ON j.id = et.entry_id
                LEFT JOIN tags t ON et.tag_id = t.id
                '''
                conditions.append("t.nom = ?")
                params.append(tag)
            
            if start_date:
                conditions.append("j.date >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("j.date <= ?")
                params.append(end_date)
            
            if entreprise_id:
                conditions.append("j.entreprise_id = ?")
                params.append(entreprise_id)
            
            if type_entree:
                conditions.append("j.type_entree = ?")
                params.append(type_entree)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            # Optimisation avec requête totale/pagination séparées
            # Récupérer le nombre total de résultats
            count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Ajouter l'ordre et la pagination
            query += " ORDER BY j.date DESC LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)
            
            cursor.execute(query, params)
            entries = [dict(row) for row in cursor.fetchall()]
            
            # Ajouter la pagination aux résultats
            pagination = {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "pages": (total_count + limit - 1) // limit,
                "current_page": (offset // limit) + 1
            }
            
            # Récupérer les tags pour chaque entrée
            for entry in entries:
                cursor.execute('''
                SELECT t.nom FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ''', (entry['id'],))
                
                entry['tags'] = [row[0] for row in cursor.fetchall()]
                # Ajouter la pagination
                entry['_pagination'] = pagination
            
            return entries
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des entrées: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération des entrées: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des entrées: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des entrées: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def search_entries(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche des entrées par similarité sémantique
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            List[Dict]: Liste des entrées les plus pertinentes
        """
        from services.llm_service import get_embeddings
        
        try:
            # Obtenir l'embedding de la requête
            embedding = await get_embeddings(query)
            
            # Rechercher dans ChromaDB
            journal_collection = get_journal_collection()
            results = journal_collection.query(
                query_embeddings=[embedding],
                n_results=limit
            )
            
            if not results or not results['ids'][0]:
                return []
            
            # Extraire les IDs des entrées
            entry_ids = []
            for id in results['ids'][0]:
                # Format: entry_{id}
                parts = id.split('_')
                if len(parts) >= 2:
                    try:
                        entry_ids.append(int(parts[1]))
                    except ValueError:
                        continue
            
            # Récupérer les entrées complètes
            entries = []
            for i, entry_id in enumerate(entry_ids):
                entry = await JournalRepository.get_entry(entry_id)
                if entry:
                    # Ajouter le score de similarité
                    entry['similarity'] = 1.0 - results['distances'][0][i] if 'distances' in results else None
                    entries.append(entry)
            
            return entries
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'entrées: {str(e)}")
            # Fallback sur une recherche par mots-clés
            return await JournalRepository._fallback_search(query, limit)
    
    @staticmethod
    async def _fallback_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche des entrées par mots-clés (fallback si la recherche vectorielle échoue)
        
        Args:
            query: Texte de recherche
            limit: Nombre maximum de résultats
            
        Returns:
            List[Dict]: Liste des entrées les plus pertinentes
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
                like_clauses.append("j.texte LIKE ?")
                params.append(f"%{keyword}%")
            
            # Construire la requête complète
            query = f'''
            SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, 
                j.entreprise_id, e.nom as entreprise_nom,
                ({"+" * len(like_clauses)}) as match_count
            FROM journal_entries j
            LEFT JOIN entreprises e ON j.entreprise_id = e.id
            WHERE {" OR ".join(like_clauses)}
            ORDER BY match_count DESC
            LIMIT ?
            '''
            
            # Remplacer les + par "CASE WHEN clause THEN 1 ELSE 0 END"
            query = query.replace("+", " + ".join([f"CASE WHEN {clause} THEN 1 ELSE 0 END" for clause in like_clauses]))
            
            params.append(limit)
            
            cursor.execute(query, params)
            entries = [dict(row) for row in cursor.fetchall()]
            
            # Récupérer les tags pour chaque entrée
            for entry in entries:
                cursor.execute('''
                SELECT t.nom FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ''', (entry['id'],))
                
                entry['tags'] = [row[0] for row in cursor.fetchall()]
                # Ajouter un score de similarité simulé
                match_count = entry.pop('match_count', 0)
                entry['similarity'] = match_count / len(keywords)
            
            return entries
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la recherche par mots-clés: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la recherche par mots-clés: {str(e)}")
            return []
        finally:
            conn.close()
    
    @staticmethod
    async def get_entreprises() -> List[Dict[str, Any]]:
        """
        Récupère la liste des entreprises
        
        Returns:
            List[Dict]: Liste des entreprises
        """
        conn = await get_db_connection()
        try:
            # Vérifier si la table entreprises existe
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entreprises'")
            if not cursor.fetchone():
                logger.error("La table 'entreprises' n'existe pas dans la base de données")
                # Créer la table si elle n'existe pas
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS entreprises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT NOT NULL,
                    date_debut TEXT NOT NULL,
                    date_fin TEXT,
                    description TEXT
                )
                ''')
                # Ajouter des entreprises par défaut
                cursor.execute('''
                INSERT INTO entreprises (nom, date_debut, date_fin, description)
                VALUES 
                ('AI Builders', '2023-09-01', '2024-08-31', 'Première année d''alternance'),
                ('Gecina', '2024-09-01', NULL, 'Deuxième année d''alternance')
                ''')
                conn.commit()
                logger.info("Table 'entreprises' créée avec des valeurs par défaut")
            
            # Récupérer les entreprises
            cursor.execute('''
            SELECT id, nom, date_debut, date_fin, description
            FROM entreprises
            ORDER BY date_debut DESC
            ''')
            
            entreprises = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Récupération de {len(entreprises)} entreprises réussie")
            
            return entreprises
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des entreprises: {str(e)}")
            # Retourner une liste vide au lieu de lever une exception pour éviter l'erreur 500
            logger.warning("Retour d'une liste vide comme solution de secours")
            return []
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des entreprises: {str(e)}")
            # Retourner une liste vide au lieu de lever une exception pour éviter l'erreur 500
            logger.warning("Retour d'une liste vide comme solution de secours")
            return []
        finally:
            conn.close()
    
    @staticmethod
    async def get_tags() -> List[Dict[str, Any]]:
        """
        Récupère la liste des tags avec leur nombre d'occurrences
        
        Returns:
            List[Dict]: Liste des tags
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT t.id, t.nom, COUNT(et.entry_id) as count
            FROM tags t
            LEFT JOIN entry_tags et ON t.id = et.tag_id
            GROUP BY t.id
            ORDER BY count DESC
            ''')
            
            tags = [dict(row) for row in cursor.fetchall()]
            return tags
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des tags: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération des tags: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tags: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des tags: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def get_import_sources() -> List[Dict[str, Any]]:
        """
        Récupère la liste des documents sources utilisés pour les imports
        
        Returns:
            List[Dict]: Liste des sources d'import avec stats
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT source_document, COUNT(*) as entry_count, MIN(date) as first_date, MAX(date) as last_date
            FROM journal_entries
            WHERE source_document IS NOT NULL AND source_document != ''
            GROUP BY source_document
            ORDER BY last_date DESC
            ''')
            
            sources = []
            for row in cursor.fetchall():
                source_dict = dict(row)
                
                # Ajouter la taille totale de texte
                cursor.execute('''
                SELECT SUM(LENGTH(texte)) as total_text_size
                FROM journal_entries
                WHERE source_document = ?
                ''', (source_dict['source_document'],))
                
                size_row = cursor.fetchone()
                source_dict['total_text_size'] = size_row['total_text_size'] if size_row else 0
                
                sources.append(source_dict)
            
            return sources
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de la récupération des sources d'import: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la récupération des sources d'import: {str(e)}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des sources d'import: {str(e)}")
            raise DatabaseError(f"Erreur lors de la récupération des sources d'import: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def delete_entries_by_source(source_document: Optional[str] = None) -> int:
        """
        Supprime les entrées de journal créées à partir d'un document source
        
        Args:
            source_document: Nom du fichier source (si None, toutes les entrées avec source)
            
        Returns:
            int: Nombre d'entrées supprimées
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            journal_collection = get_journal_collection()
            
            # Récupérer les IDs des entrées à supprimer
            if source_document:
                cursor.execute('''
                SELECT id FROM journal_entries 
                WHERE source_document = ?
                ''', (source_document,))
            else:
                cursor.execute('''
                SELECT id FROM journal_entries 
                WHERE source_document IS NOT NULL AND source_document != ''
                ''')
            
            entries_to_delete = [row['id'] for row in cursor.fetchall()]
            
            if not entries_to_delete:
                return 0
            
            # Pour chaque entrée, supprimer de ChromaDB
            for entry_id in entries_to_delete:
                try:
                    journal_collection.delete(ids=[f"entry_{entry_id}"])
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression dans ChromaDB (ID {entry_id}): {str(e)}")
            
            # Supprimer les entrées de la base SQLite
            if source_document:
                cursor.execute('''
                DELETE FROM journal_entries 
                WHERE source_document = ?
                ''', (source_document,))
            else:
                cursor.execute('''
                DELETE FROM journal_entries 
                WHERE source_document IS NOT NULL AND source_document != ''
                ''')
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la suppression des entrées par source: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la suppression des entrées par source: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la suppression des entrées par source: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression des entrées par source: {str(e)}")
        finally:
            conn.close()
    
    @staticmethod
    async def delete_entries_by_date(start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
        """
        Supprime les entrées de journal dans une plage de dates
        
        Args:
            start_date: Date de début (format YYYY-MM-DD), optionnel
            end_date: Date de fin (format YYYY-MM-DD), optionnel
            
        Returns:
            int: Nombre d'entrées supprimées
        """
        if not start_date and not end_date:
            raise ValueError("Au moins une date (début ou fin) doit être spécifiée")
            
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            journal_collection = get_journal_collection()
            
            # Construction de la requête en fonction des paramètres fournis
            query = "SELECT id FROM journal_entries WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
                
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
                
            # Récupérer les IDs des entrées à supprimer
            cursor.execute(query, params)
            entries_to_delete = [row['id'] for row in cursor.fetchall()]
            
            if not entries_to_delete:
                return 0
            
            # Pour chaque entrée, supprimer de ChromaDB
            for entry_id in entries_to_delete:
                try:
                    journal_collection.delete(ids=[f"entry_{entry_id}"])
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression dans ChromaDB (ID {entry_id}): {str(e)}")
            
            # Supprimer les entrées de la base SQLite
            delete_query = "DELETE FROM journal_entries WHERE 1=1"
            if start_date:
                delete_query += " AND date >= ?"
            if end_date:
                delete_query += " AND date <= ?"
                
            cursor.execute(delete_query, params)
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la suppression des entrées par date: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la suppression des entrées par date: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la suppression des entrées par date: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression des entrées par date: {str(e)}")
        finally:
            conn.close()
            
    @staticmethod
    async def delete_all_entries() -> int:
        """
        Supprime toutes les entrées de journal
        
        Returns:
            int: Nombre d'entrées supprimées
        """
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            journal_collection = get_journal_collection()
            
            # Récupérer le nombre d'entrées avant suppression
            cursor.execute("SELECT COUNT(*) FROM journal_entries")
            count_before = cursor.fetchone()[0]
            
            if count_before == 0:
                return 0
                
            # Récupérer tous les IDs des entrées
            cursor.execute("SELECT id FROM journal_entries")
            entries_to_delete = [row['id'] for row in cursor.fetchall()]
            
            # Pour chaque entrée, supprimer de ChromaDB
            for entry_id in entries_to_delete:
                try:
                    journal_collection.delete(ids=[f"entry_{entry_id}"])
                except Exception as e:
                    logger.error(f"Erreur lors de la suppression dans ChromaDB (ID {entry_id}): {str(e)}")
            
            # Vider la table des entrées
            cursor.execute("DELETE FROM journal_entries")
            deleted_count = cursor.rowcount
            
            # Nettoyer les tables associées
            cursor.execute("DELETE FROM entry_tags")
            
            conn.commit()
            
            return count_before
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Erreur SQLite lors de la suppression de toutes les entrées: {str(e)}")
            raise DatabaseError(f"Erreur SQLite lors de la suppression de toutes les entrées: {str(e)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la suppression de toutes les entrées: {str(e)}")
            raise DatabaseError(f"Erreur lors de la suppression de toutes les entrées: {str(e)}")
        finally:
            conn.close()