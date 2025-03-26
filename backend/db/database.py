import os
import sqlite3
import asyncio
import logging
import time
from typing import Dict, Any, Optional
import chromadb

from core.config import settings

logger = logging.getLogger(__name__)

async def get_db_connection():
    """Établit une connexion asynchrone à la base de données SQLite"""
    def _get_connection():
        try:
            os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
            conn = sqlite3.connect(settings.SQLITE_DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Erreur lors de la connexion à la base de données: {e}")
            # En cas d'erreur, on peut tenter une connexion en mémoire pour éviter un crash
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
    
    return await asyncio.to_thread(_get_connection)

# Variables globales pour les collections ChromaDB
chroma_client = None
journal_collection = None
sections_collection = None

def initialize_db(max_retries=5):
    """Initialisation robuste de la base de données avec gestion des erreurs et réessais"""
    for retry in range(max_retries):
        try:
            logger.info(f"Initialisation de la base de données (tentative {retry+1}/{max_retries})...")
            os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
            conn = sqlite3.connect(settings.SQLITE_DB_PATH, check_same_thread=False)
            cursor = conn.cursor()
            
            # Création des tables (schéma de base de données)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS entreprises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT,
                description TEXT
            )
            ''')
            
            # Création de la table journal_entries
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                texte TEXT NOT NULL,
                entreprise_id INTEGER,
                type_entree TEXT NOT NULL DEFAULT 'quotidien',
                source_document TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises (id)
            )
            ''')
            
            # Création de la table tags
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE
            )
            ''')
            
            # Création de la table d'association entry_tags
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_tags (
                entry_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (entry_id, tag_id),
                FOREIGN KEY (entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (id)
            )
            ''')
            
            # Création de la table memoire_sections
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS memoire_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre TEXT NOT NULL,
                contenu TEXT,
                ordre INTEGER NOT NULL DEFAULT 0,
                parent_id INTEGER,
                derniere_modification TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES memoire_sections (id) ON DELETE SET NULL
            )
            ''')
            
            # Création de la table d'association section_entries
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_entries (
                section_id INTEGER NOT NULL,
                entry_id INTEGER NOT NULL,
                PRIMARY KEY (section_id, entry_id),
                FOREIGN KEY (section_id) REFERENCES memoire_sections (id) ON DELETE CASCADE,
                FOREIGN KEY (entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE
            )
            ''')
            
            # ... (autres tables)
            
            # Vérifier si des entreprises par défaut doivent être ajoutées
            cursor.execute("SELECT COUNT(*) FROM entreprises")
            if cursor.fetchone()[0] == 0:
                logger.info("Ajout des entreprises par défaut...")
                cursor.execute('''
                INSERT INTO entreprises (nom, date_debut, date_fin, description)
                VALUES 
                ('AI Builders', '2023-09-01', '2024-08-31', 'Première année d''alternance'),
                ('Gecina', '2024-09-01', NULL, 'Deuxième année d''alternance')
                ''')
                logger.info("Entreprises par défaut ajoutées.")
                
            conn.commit()
            conn.close()
            logger.info("Base de données initialisée avec succès.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Erreur SQLite lors de l'initialisation de la base de données (tentative {retry+1}/{max_retries}): {str(e)}")
            if retry < max_retries - 1:
                logger.info(f"Nouvelle tentative dans 2 secondes...")
                time.sleep(2)
            else:
                logger.critical("Impossible d'initialiser la base de données après plusieurs tentatives.")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
            if retry < max_retries - 1:
                logger.info(f"Nouvelle tentative dans 2 secondes...")
                time.sleep(2)
            else:
                return False

def initialize_vectordb(max_retries=5):
    """Initialisation robuste de ChromaDB avec gestion des erreurs et réessais"""
    global chroma_client, journal_collection, sections_collection
    
    for retry in range(max_retries):
        try:
            logger.info(f"Initialisation de ChromaDB (tentative {retry+1}/{max_retries})...")
            os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
            
            # Nouvelle configuration recommandée pour ChromaDB
            chroma_client = chromadb.PersistentClient(
                path=settings.VECTOR_DB_PATH
            )
            
            # Création ou récupération des collections
            try:
                journal_collection = chroma_client.get_collection("journal_entries")
                logger.info("Collection ChromaDB 'journal_entries' récupérée.")
            except Exception:
                journal_collection = chroma_client.create_collection("journal_entries")
                logger.info("Collection ChromaDB 'journal_entries' créée.")
            
            try:
                sections_collection = chroma_client.get_collection("memoire_sections")
                logger.info("Collection ChromaDB 'memoire_sections' récupérée.")
            except Exception:
                sections_collection = chroma_client.create_collection("memoire_sections")
                logger.info("Collection ChromaDB 'memoire_sections' créée.")
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de ChromaDB (tentative {retry+1}/{max_retries}): {str(e)}")
            if retry < max_retries - 1:
                logger.info(f"Nouvelle tentative dans 2 secondes...")
                time.sleep(2)
            else:
                logger.warning("Impossible d'initialiser ChromaDB, utilisation du mode de secours...")
                # Fallback sur une implémentation simulée
                from utils.dummy_vectordb import create_dummy_collections
                chroma_client, journal_collection, sections_collection = create_dummy_collections()
                return False

def get_journal_collection():
    """Récupère la collection journal_entries de ChromaDB"""
    global journal_collection
    if journal_collection is None:
        initialize_vectordb()
    return journal_collection

def get_sections_collection():
    """Récupère la collection memoire_sections de ChromaDB"""
    global sections_collection
    if sections_collection is None:
        initialize_vectordb()
    return sections_collection