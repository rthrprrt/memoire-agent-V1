# tests/conftest.py
import os
import sys
import pytest
import sqlite3
import asyncio
from pathlib import Path

# S'assurer que le répertoire parent est dans le chemin (pour les imports)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import initialize_db, initialize_vectordb
from core.config import settings

# Remplacer les chemins pour les tests
settings.SQLITE_DB_PATH = "test_data/test_memoire.db"
settings.VECTOR_DB_PATH = "test_data/test_vectordb"
settings.EXPORT_PATH = "test_data/test_exports"

# Créer les répertoires pour les tests
os.makedirs("test_data", exist_ok=True)
os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
os.makedirs(settings.VECTOR_DB_PATH, exist_ok=True)
os.makedirs(settings.EXPORT_PATH, exist_ok=True)

# Mock de la base de données
@pytest.fixture
def mock_db():
    """Crée une base de données SQLite in-memory pour les tests"""
    # Créer une connexion à une base de données en mémoire
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Créer les tables
    cursor = conn.cursor()
    
    # Table entreprises
    cursor.execute('''
    CREATE TABLE entreprises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        date_debut TEXT NOT NULL,
        date_fin TEXT,
        description TEXT
    )
    ''')
    
    # Table journal_entries
    cursor.execute('''
    CREATE TABLE journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        texte TEXT NOT NULL,
        entreprise_id INTEGER,
        type_entree TEXT DEFAULT 'quotidien',
        source_document TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (entreprise_id) REFERENCES entreprises(id)
    )
    ''')
    
    # Table tags
    cursor.execute('''
    CREATE TABLE tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE
    )
    ''')
    
    # Table entry_tags
    cursor.execute('''
    CREATE TABLE entry_tags (
        entry_id INTEGER,
        tag_id INTEGER,
        PRIMARY KEY (entry_id, tag_id),
        FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    )
    ''')
    
    # Table memoire_sections
    cursor.execute('''
    CREATE TABLE memoire_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        contenu TEXT,
        ordre INTEGER NOT NULL,
        parent_id INTEGER,
        derniere_modification TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES memoire_sections(id)
    )
    ''')
    
    # Table section_entries
    cursor.execute('''
    CREATE TABLE section_entries (
        section_id INTEGER,
        entry_id INTEGER,
        PRIMARY KEY (section_id, entry_id),
        FOREIGN KEY (section_id) REFERENCES memoire_sections(id) ON DELETE CASCADE,
        FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
    )
    ''')
    
    # Table bibliography_references
    cursor.execute('''
    CREATE TABLE bibliography_references (
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
    
    # Ajouter des données de test
    cursor.execute('''
    INSERT INTO entreprises (nom, date_debut, date_fin, description)
    VALUES ('Entreprise Test', '2023-01-01', '2023-12-31', 'Description de test')
    ''')
    
    conn.commit()
    
    yield conn
    
    # Fermer la connexion après les tests
    conn.close()

# Mock du repository journal
@pytest.fixture
def mock_journal_repository(mock_db):
    from db.repositories.journal_repository import JournalRepository
    
    # Surcharger la méthode get_db_connection
    async def get_mock_db_connection():
        return mock_db
    
    # Remplacer temporairement get_db_connection
    original_get_connection = JournalRepository.get_db_connection
    JournalRepository.get_db_connection = get_mock_db_connection
    
    yield JournalRepository
    
    # Restaurer la méthode originale
    JournalRepository.get_db_connection = original_get_connection

# Mock du repository mémoire
@pytest.fixture
def mock_memoire_repository(mock_db):
    from db.repositories.memoire_repository import MemoireRepository
    
    # Surcharger la méthode get_db_connection
    async def get_mock_db_connection():
        return mock_db
    
    # Remplacer temporairement get_db_connection
    original_get_connection = MemoireRepository.get_db_connection
    MemoireRepository.get_db_connection = get_mock_db_connection
    
    yield MemoireRepository
    
    # Restaurer la méthode originale
    MemoireRepository.get_db_connection = original_get_connection

# Mock du service memory_manager
@pytest.fixture
def mock_memory_manager(mock_journal_repository, mock_memoire_repository):
    from services.memory_manager import MemoryManager
    
    # Créer un MemoryManager avec les repositories mockés
    memory_manager = MemoryManager(
        journal_repository=mock_journal_repository,
        memoire_repository=mock_memoire_repository
    )
    
    return memory_manager

# Client de test pour FastAPI
@pytest.fixture
async def test_client():
    from fastapi.testclient import TestClient
    from main import app
    
    client = TestClient(app)
    return client

# Pour les tests asynchrones
@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()