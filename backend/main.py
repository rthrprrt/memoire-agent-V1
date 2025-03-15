import os
import json
import sqlite3
import hashlib
import threading
import pickle
import logging
from datetime import datetime
from typing import List, Optional, AsyncGenerator, Dict, Any, Callable
import re
import asyncio
import httpx
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Depends, Response, status, Body, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import httpx
import chromadb
import time
import uuid
import random

# Mise à jour de l'import de Pydantic avec les outils de validation
from pydantic import BaseModel, constr, Field, validator

from export_manager import MemoryExporter, ExportOptions
from langchain.text_splitter import RecursiveCharacterTextSplitter
from backup_manager import BackupManager

# Import des modèles définis dans models.py
try:
    from models import PDFImportResponse, GeneratePlanRequest, GenerateContentRequest, ImproveTextRequest, HallucinationDetector
except ImportError:
    # Si l'import échoue, les définitions seront ajoutées par le script init.sh
    pass

# Configuration du logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Création de l'application FastAPI
app = FastAPI(
    title="API Assistant de Rédaction de Mémoire",
    description="API pour l'assistant de rédaction de mémoire professionnel",
    version="1.0.0"
)

# ---------------------------------------------------------------------
# 1. Configuration CORS sécurisée
# ---------------------------------------------------------------------
def configure_cors(app: FastAPI):
    """Configure les CORS de manière sécurisée pour l'application"""
    origins = [
        "http://localhost:8501",  # Frontend Streamlit local
        "http://frontend:8501",   # Frontend dans Docker
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )

configure_cors(app)

# ---------------------------------------------------------------------
# 2. Modèles Pydantic avec validation renforcée
# ---------------------------------------------------------------------
class JournalEntry(BaseModel):
    date: datetime
    texte: constr(min_length=10, max_length=10000)
    entreprise_id: Optional[int] = None
    type_entree: Optional[str] = "quotidien"
    source_document: Optional[str] = None
    tags: Optional[List[constr(min_length=1, max_length=50)]] = None

    class Config:
        extra = "forbid"  # Interdire les champs supplémentaires non déclarés

    @validator('texte')
    def texte_must_be_safe(cls, v):
        """Vérifie que le texte ne contient pas de code malveillant"""
        if re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

    @validator('tags', each_item=True)
    def tag_must_be_valid(cls, v):
        """Vérifie que chaque tag est valide (lettres, chiffres, tirets, underscores et espaces autorisés)"""
        if not re.match(r'^[a-zA-Z0-9\-_\s]+$', v):
            raise ValueError(f"Tag invalide: {v}. Utiliser uniquement des lettres, chiffres, tirets et underscores")
        return v


class MemoireSection(BaseModel):
    titre: constr(min_length=3, max_length=200)
    contenu: Optional[constr(max_length=50000)] = None
    ordre: int = Field(..., ge=0, lt=1000)
    parent_id: Optional[int] = None

    class Config:
        extra = "forbid"

    @validator('contenu')
    def contenu_must_be_safe(cls, v):
        """Vérifie que le contenu ne contient pas de code malveillant"""
        if v and re.search(r'<script|javascript:|onerror=|onclick=|onload=', v, re.IGNORECASE):
            raise ValueError("Contenu potentiellement dangereux détecté")
        return v

class PDFImportResponse(BaseModel):
    entries: List[dict]
    message: str
    
    class Config:
        extra = "forbid"

class GeneratePlanRequest(BaseModel):
    prompt: str
    
    class Config:
        extra = "forbid"

class GenerateContentRequest(BaseModel):
    section_id: str
    prompt: Optional[str] = None
    
    class Config:
        extra = "forbid"

class ImproveTextRequest(BaseModel):
    texte: str
    mode: str = "grammar"  # grammar, style, conciseness, etc.
    
    class Config:
        extra = "forbid"

class HallucinationDetector:
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
        
    async def check_content(self, content, context):
        # Placeholder implementation
        return {
            "has_hallucinations": False,
            "confidence_score": 0.95,
            "suspect_segments": [],
            "verified_facts": [{"text": "Sample verified fact", "confidence": 0.98}],
            "corrected_content": content
        }

# --- Classe AdaptiveTextSplitter pour un chunking adaptatif ---
class AdaptiveTextSplitter:
    """
    Splitter de texte adaptatif qui prend en compte la structure
    et le contenu sémantique du texte pour un découpage intelligent.
    """
    def __init__(self):
        # Différentes stratégies de chunking selon le type de contenu
        self.splitters = {
            "default": RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ". ", ", ", " ", ""]
            ),
            "long_form": RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=150,
                length_function=len,
                separators=["\n\n", "\n", ". ", ", ", " ", ""]
            ),
            "list": RecursiveCharacterTextSplitter(
                chunk_size=300,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ". ", ", ", " ", ""]
            ),
            "technical": RecursiveCharacterTextSplitter(
                chunk_size=400,
                chunk_overlap=100,
                length_function=len,
                separators=["\n\n", "\n", "; ", ". ", ", ", " ", ""]
            )
        }
        
        # Patterns pour détecter différents types de contenu
        self.content_patterns = {
            "list": r'(?:^|\n)(?:\d+\.\s|\*\s|-\s|\[\s?\]|\[\w\])',
            "technical": r'(?:import|def|class|function|var|const|if|for|while|try|except|\{|\}|console\.log)',
            "long_form": r'(?:(?:\w+\s){20,})'
        }
    
    def split_text(self, text: str) -> List[str]:
        content_type = self._determine_content_type(text)
        splitter = self.splitters.get(content_type, self.splitters["default"])
        return splitter.split_text(text)
    
    def split_texts(self, texts: List[str]) -> List[str]:
        all_chunks = []
        for text in texts:
            chunks = self.split_text(text)
            all_chunks.extend(chunks)
        return all_chunks
    
    def _determine_content_type(self, text: str) -> str:
        scores = {
            "list": 0,
            "technical": 0,
            "long_form": 0,
            "default": 1
        }
        
        for content_type, pattern in self.content_patterns.items():
            matches = re.findall(pattern, text)
            scores[content_type] = len(matches)
        
        line_ratio = text.count('\n') / max(1, len(text))
        if line_ratio > 0.05:
            scores["list"] += 3
        
        sentences = re.split(r'[.!?]+', text)
        avg_sentence_length = sum(len(s) for s in sentences) / max(1, len(sentences))
        if avg_sentence_length > 150:
            scores["long_form"] += 5
        elif avg_sentence_length < 60:
            scores["list"] += 2
        
        if re.search(r'[<>$%#@{}()\[\]+=]', text):
            scores["technical"] += 3
        
        return max(scores.items(), key=lambda x: x[1])[0]

# --- Implémentation du Circuit Breaker ---
class CircuitBreakerOpenError(Exception):
    """Exception levée quand un circuit est ouvert"""
    pass

class CircuitBreaker:
    """Implémentation du pattern Circuit Breaker pour protéger contre les appels répétés à un service défaillant"""
    
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"
    
    def __init__(self, name, failure_threshold=5, reset_timeout=60, half_open_max_calls=1):
        self.name = name
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.half_open_max_calls = half_open_max_calls
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialisé avec seuil={failure_threshold}, timeout={reset_timeout}s")
    
    async def __aenter__(self):
        await self._before_call()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self._on_failure()
        else:
            await self._on_success()
        return False
    
    async def _before_call(self):
        async with self._lock:
            current_time = time.time()
            
            if self.state == self.OPEN:
                if current_time - self.last_failure_time > self.reset_timeout:
                    logger.info(f"Circuit '{self.name}' passe de OPEN à HALF_OPEN après {self.reset_timeout}s")
                    self.state = self.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit '{self.name}' ouvert, attendre {int(self.reset_timeout - (current_time - self.last_failure_time))}s"
                    )
            
            if self.state == self.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' en demi-ouverture, limite d'appels de test atteinte"
                )
            
            if self.state == self.HALF_OPEN:
                self.half_open_calls += 1
    
    async def _on_success(self):
        async with self._lock:
            if self.state == self.HALF_OPEN:
                logger.info(f"Circuit '{self.name}' passe de HALF_OPEN à CLOSED après un appel réussi")
                self.state = self.CLOSED
            self.failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit '{self.name}' passe de CLOSED à OPEN après {self.failure_count} échecs"
                )
                self.state = self.OPEN
            
            if self.state == self.HALF_OPEN:
                logger.warning(f"Circuit '{self.name}' passe de HALF_OPEN à OPEN après un échec")
                self.state = self.OPEN

# Circuit breakers globaux
generation_circuit = CircuitBreaker("ollama_generation")
embedding_circuit = CircuitBreaker("ollama_embedding")

# --- Initialisation de la base de données ---
def get_db_connection():
    try:
        os.makedirs("data", exist_ok=True)
        conn = sqlite3.connect("data/memoire.db")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Erreur lors de la connexion à la base de données: {e}")
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

def init_db(max_retries=5):
    """
    Initialisation robuste de la base de données avec gestion des erreurs et réessais
    """
    for retry in range(max_retries):
        try:
            logger.info(f"Initialisation de la base de données (tentative {retry+1}/{max_retries})...")
            os.makedirs("data", exist_ok=True)
            conn = sqlite3.connect("data/memoire.db")
            cursor = conn.cursor()
            
            # Création des tables
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS entreprises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                date_debut TEXT NOT NULL,
                date_fin TEXT,
                description TEXT
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS journal_entries (
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
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_tags (
                entry_id INTEGER,
                tag_id INTEGER,
                PRIMARY KEY (entry_id, tag_id),
                FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS memoire_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titre TEXT NOT NULL,
                contenu TEXT,
                ordre INTEGER NOT NULL,
                parent_id INTEGER,
                derniere_modification TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES memoire_sections(id)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_entries (
                section_id INTEGER,
                entry_id INTEGER,
                PRIMARY KEY (section_id, entry_id),
                FOREIGN KEY (section_id) REFERENCES memoire_sections(id) ON DELETE CASCADE,
                FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
            )
            ''')
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
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS citations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id TEXT NOT NULL,
                reference_id TEXT NOT NULL,
                citation_text TEXT NOT NULL,
                location TEXT,
                FOREIGN KEY (section_id) REFERENCES memoire_sections(id),
                FOREIGN KEY (reference_id) REFERENCES bibliography_references(id)
            )
            ''')
            
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

# --- Initialisation de ChromaDB ---
def init_chromadb(max_retries=5):
    """
    Initialisation robuste de ChromaDB avec gestion des erreurs et réessais
    """
    for retry in range(max_retries):
        try:
            logger.info(f"Initialisation de ChromaDB (tentative {retry+1}/{max_retries})...")
            os.makedirs("data/chromadb", exist_ok=True)
            
            # Nouvelle configuration recommandée pour ChromaDB
            chromadb_client = chromadb.PersistentClient(
                path="data/chromadb"
            )
            
            # Création ou récupération des collections
            try:
                journal_collection = chromadb_client.get_collection("journal_entries")
                logger.info("Collection ChromaDB 'journal_entries' récupérée.")
            except Exception:
                journal_collection = chromadb_client.create_collection("journal_entries")
                logger.info("Collection ChromaDB 'journal_entries' créée.")
            
            try:
                sections_collection = chromadb_client.get_collection("memoire_sections")
                logger.info("Collection ChromaDB 'memoire_sections' récupérée.")
            except Exception:
                sections_collection = chromadb_client.create_collection("memoire_sections")
                logger.info("Collection ChromaDB 'memoire_sections' créée.")
            
            return chromadb_client, journal_collection, sections_collection
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de ChromaDB (tentative {retry+1}/{max_retries}): {str(e)}")
            if retry < max_retries - 1:
                logger.info(f"Nouvelle tentative dans 2 secondes...")
                time.sleep(2)
            else:
                logger.warning("Impossible d'initialiser ChromaDB, utilisation du mode de secours...")
                # Fallback sur une implémentation simulée si ChromaDB ne fonctionne pas
                class DummyCollection:
                    def add(self, *args, **kwargs):
                        logger.warning("ChromaDB n'est pas disponible. Opération simulée.")
                        return None
                    def query(self, *args, **kwargs):
                        logger.warning("ChromaDB n'est pas disponible. Opération simulée.")
                        return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}
                    def update(self, *args, **kwargs):
                        logger.warning("ChromaDB n'est pas disponible. Opération simulée.")
                        return None
                    def delete(self, *args, **kwargs):
                        logger.warning("ChromaDB n'est pas disponible. Opération simulée.")
                        return None
                    def get(self, *args, **kwargs):
                        logger.warning("ChromaDB n'est pas disponible. Opération simulée.")
                        return {"ids": [], "metadatas": [], "documents": []}
                
                class DummyClient:
                    def get_collection(self, name):
                        return DummyCollection()
                    def create_collection(self, name):
                        return DummyCollection()
                    def get_or_create_collection(self, name):
                        return DummyCollection()
                
                return DummyClient(), DummyCollection(), DummyCollection()

# Initialisation de la base de données et de ChromaDB
try:
    if not init_db():
        logger.critical("Échec de l'initialisation de la base de données, mais l'application va tenter de démarrer quand même.")
except Exception as e:
    logger.critical(f"Exception non gérée lors de l'initialisation de la base de données: {str(e)}")

try:
    chromadb_client, journal_collection, sections_collection = init_chromadb()
except Exception as e:
    logger.critical(f"Exception non gérée lors de l'initialisation de ChromaDB: {str(e)}")
    # Définir des fallbacks en cas d'échec complet
    class DummyCollection:
        def add(self, *args, **kwargs): return None
        def query(self, *args, **kwargs): return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}
        def update(self, *args, **kwargs): return None
        def delete(self, *args, **kwargs): return None
        def get(self, *args, **kwargs): return {"ids": [], "metadatas": [], "documents": []}
    
    journal_collection = DummyCollection()
    sections_collection = DummyCollection()

# --- Classe MemoryManager avec transactions atomiques ---
class MemoryManager:
    def __init__(self, db_path: str = "data/memoire.db", chroma_collection=journal_collection):
        self.db_path = db_path
        self.chroma_collection = chroma_collection
        self.text_splitter = AdaptiveTextSplitter()
        try:
            self.sections_collection = chromadb_client.get_collection("memoire_sections")
            print("Collection ChromaDB 'memoire_sections' récupérée.")
        except Exception:
            self.sections_collection = chromadb_client.create_collection("memoire_sections")
            print("Collection ChromaDB 'memoire_sections' créée.")

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_journal_entry(self, entry: JournalEntry) -> dict:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            entreprise_id = entry.entreprise_id
            if entreprise_id is None:
                cursor.execute('''
                SELECT id FROM entreprises 
                WHERE date_debut <= ? AND (date_fin IS NULL OR date_fin >= ?)
                ''', (entry.date, entry.date))
                result = cursor.fetchone()
                if result:
                    entreprise_id = result[0]
            tags = entry.tags
            if not tags:
                tags = extract_automatic_tags(entry.texte)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
            INSERT INTO journal_entries (date, texte, entreprise_id, type_entree, source_document, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (entry.date, entry.texte, entreprise_id, entry.type_entree, entry.source_document, now))
            entry_id = cursor.lastrowid
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
            try:
                self.chroma_collection.add(
                    documents=[entry.texte],
                    metadatas=[{"date": entry.date, "entry_id": entry_id}],
                    ids=[f"entry_{entry_id}"]
                )
            except Exception as e:
                conn.rollback()
                raise Exception(f"Erreur lors de l'ajout à ChromaDB: {str(e)}")
            conn.commit()
            cursor.execute('''
            SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, j.entreprise_id
            FROM journal_entries j
            WHERE j.id = ?
            ''', (entry_id,))
            inserted_entry = dict(cursor.fetchone())
            cursor.execute('''
            SELECT t.nom FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id = ?
            ''', (entry_id,))
            inserted_entry['tags'] = [row[0] for row in cursor.fetchall()]
            return inserted_entry
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_journal_entry(self, entry_id: int, entry: JournalEntry) -> dict:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
            if not cursor.fetchone():
                raise Exception("Entrée non trouvée")
            cursor.execute('''
            UPDATE journal_entries 
            SET date = ?, texte = ?, entreprise_id = ?, type_entree = ?, source_document = ?
            WHERE id = ?
            ''', (entry.date, entry.texte, entry.entreprise_id, entry.type_entree, entry.source_document, entry_id))
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
            try:
                self.chroma_collection.update(
                    documents=[entry.texte],
                    metadatas=[{"date": entry.date, "entry_id": entry_id}],
                    ids=[f"entry_{entry_id}"]
                )
            except Exception as e:
                conn.rollback()
                raise Exception(f"Erreur lors de la mise à jour dans ChromaDB: {str(e)}")
            conn.commit()
            cursor.execute('''
            SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, j.entreprise_id
            FROM journal_entries j
            WHERE j.id = ?
            ''', (entry_id,))
            updated_entry = dict(cursor.fetchone())
            cursor.execute('''
            SELECT t.nom FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id = ?
            ''', (entry_id,))
            updated_entry['tags'] = [row[0] for row in cursor.fetchall()]
            return updated_entry
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_journal_entry(self, entry_id: int):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
            if not cursor.fetchone():
                raise Exception("Entrée non trouvée")
            cursor.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
            try:
                self.chroma_collection.delete(ids=[f"entry_{entry_id}"])
            except Exception as e:
                conn.rollback()
                raise Exception(f"Erreur lors de la suppression dans ChromaDB: {str(e)}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # --- Méthodes ajoutées pour le support du chunking adaptatif ---
    async def _index_section_content(self, section: MemoireSection, is_repair: bool = False):
        """Indexe le contenu d'une section dans ChromaDB avec chunking adaptatif"""
        chunks = self.text_splitter.split_text(section.contenu or "")
        try:
            self.sections_collection.delete(where={"section_id": section.id})
        except Exception as e:
            logger.warning(f"Erreur lors de la suppression des chunks existants: {str(e)}")
        
        if chunks:
            ids = [f"{section.id}_{i}" for i in range(len(chunks))]
            metadata = []
            for i, chunk in enumerate(chunks):
                chunk_type = self.text_splitter._determine_content_type(chunk)
                keywords = self._extract_keywords(chunk)
                metadata.append({
                    "section_id": section.id,
                    "title": section.titre,
                    "chunk_index": i,
                    "chunk_type": chunk_type,
                    "keywords": ",".join(keywords[:10]),
                    "chunk_size": len(chunk),
                    "timestamp": datetime.now().isoformat()
                })
            self.sections_collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadata
            )
            logger.info(f"Indexé {len(chunks)} chunks pour la section {section.id}")

    def _extract_keywords(self, text: str) -> List[str]:
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()
        stopwords = {"le", "la", "les", "un", "une", "des", "et", "ou", "a", "à", "de", "du", "en", "est", "ce", "que", "qui", "dans", "par", "pour", "sur", "avec", "sans", "il", "elle", "ils", "elles", "nous", "vous", "je", "tu"}
        keywords = [word for word in words if word not in stopwords and len(word) > 3]
        keyword_counts = {}
        for word in keywords:
            keyword_counts[word] = keyword_counts.get(word, 0) + 1
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_keywords]

    async def get_section(self, section_id: int):
        def query_section():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memoire_sections WHERE id = ?", (section_id,))
            section = cursor.fetchone()
            conn.close()
            if section:
                return dict(section)
            else:
                raise HTTPException(status_code=404, detail="Section non trouvée")
        return await asyncio.to_thread(query_section)

    async def search_relevant_journal(self, query: str):
        def query_journal():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_entries ORDER BY date DESC LIMIT 5")
            entries = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return entries
        return await asyncio.to_thread(query_journal)

    async def get_outline(self):
        def query_outline():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memoire_sections WHERE parent_id IS NULL ORDER BY ordre")
            outline = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return outline
        return await asyncio.to_thread(query_outline)

    async def save_section(self, section: dict):
        def update_section():
            conn = get_db_connection()
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("UPDATE memoire_sections SET contenu = ?, derniere_modification = ? WHERE id = ?", (section["contenu"], now, section["id"]))
            conn.commit()
            conn.close()
        await asyncio.to_thread(update_section)

# Instance globale de MemoryManager
memory_manager = MemoryManager()

# Extraction automatique de tags
def extract_automatic_tags(texte, threshold=0.01):
    import re
    from collections import Counter
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', texte.lower())
    stopwords = set(['dans', 'avec', 'pour', 'cette', 'mais', 'avoir', 'faire', 
                     'plus', 'tout', 'bien', 'être', 'comme', 'nous', 'leur', 'sans', 'vous', 'dont'])
    words = [w for w in words if w not in stopwords]
    word_counts = Counter(words)
    total_words = len(words)
    if total_words == 0:
        return []
    potential_tags = [word for word, count in word_counts.items() if count / total_words > threshold]
    return potential_tags[:5]

# --- Endpoints et routes API ---

# --- Remplacement de l'initialisation de OllamaManager par LLMOrchestrator ---
from llm_orchestrator import LLMOrchestrator
llm_orchestrator = LLMOrchestrator(
    base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
)

# --- Endpoints PDF ---
@app.get("/")
async def root():
    """Endpoint racine retournant un message d'accueil"""
    return {"message": "Bienvenue sur l'API de l'assistant de rédaction de mémoire professionnel"}

@app.post("/import/pdf", response_model=PDFImportResponse)
async def import_pdf(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    try:
        contents = await file.read()
        entries = process_pdf_file(contents, file.filename)
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        if entreprise_id is not None:
            for entry in entries:
                entry["entreprise_id"] = entreprise_id
        added_entries = []
        for entry in entries:
            result = await asyncio.to_thread(memory_manager.add_journal_entry, JournalEntry(**entry))
            if result:
                added_entries.append(result)
        return {
            "entries": added_entries,
            "message": f"{len(added_entries)} entrées ajoutées avec succès."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du PDF: {str(e)}")

@app.post("/import/pdf/analyze", response_model=List[dict])
async def analyze_pdf(
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    try:
        contents = await file.read()
        entries = process_pdf_file(contents, file.filename)
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du PDF: {str(e)}")

# --- Endpoints Journal ---
@app.post("/journal/entries")
async def add_journal_entry_endpoint(entry: JournalEntry):
    try:
        result = await asyncio.to_thread(memory_manager.add_journal_entry, entry)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/journal/entries/{entry_id}")
async def update_journal_entry_endpoint(entry_id: int, entry: JournalEntry):
    try:
        result = await asyncio.to_thread(memory_manager.update_journal_entry, entry_id, entry)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/journal/entries/{entry_id}")
async def delete_journal_entry_endpoint(entry_id: int):
    try:
        await asyncio.to_thread(memory_manager.delete_journal_entry, entry_id)
        return {"status": "success", "message": "Entrée supprimée avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/journal/entries")
async def get_journal_entries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    entreprise_id: Optional[int] = None,
    type_entree: Optional[str] = None,
    tag: Optional[str] = None
):
    """Liste les entrées du journal avec filtres optionnels"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = '''
    SELECT DISTINCT j.id, j.date, j.texte as content, j.type_entree, j.source_document, 
           j.entreprise_id, e.nom as entreprise_nom
    FROM journal_entries j
    LEFT JOIN entreprises e ON j.entreprise_id = e.id
    '''
    params = []
    conditions = []
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
    query += " ORDER BY j.date DESC"
    cursor.execute(query, params)
    entries = [dict(row) for row in cursor.fetchall()]
    for entry in entries:
        cursor.execute('''
        SELECT t.nom FROM tags t
        JOIN entry_tags et ON t.id = et.tag_id
        WHERE et.entry_id = ?
        ''', (entry['id'],))
        entry['tags'] = [row[0] for row in cursor.fetchall()]
    conn.close()
    return entries

@app.get("/journal/entries/{entry_id}")
async def get_journal_entry(entry_id: int):
    conn = get_db_connection()
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
        raise HTTPException(status_code=404, detail="Entrée non trouvée")
    result = dict(entry)
    cursor.execute('''
    SELECT t.nom FROM tags t
    JOIN entry_tags et ON t.id = et.tag_id
    WHERE et.entry_id = ?
    ''', (entry_id,))
    result['tags'] = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result

@app.get("/entreprises")
async def get_entreprises():
    """Liste toutes les entreprises"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nom, date_debut, date_fin, description FROM entreprises")
    entreprises = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return entreprises

@app.get("/tags")
async def get_tags():
    """Liste tous les tags avec leur nombre d'occurrences"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.id, t.nom, COUNT(et.entry_id) as count
    FROM tags t
    LEFT JOIN entry_tags et ON t.id = et.tag_id
    GROUP BY t.id
    ORDER BY count DESC
    ''')
    tags = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tags

# --- Endpoint de recherche modifié pour utiliser l'orchestrateur pour les embeddings ---
@app.get("/search")
async def search_entries(query: str, limit: int = 5):
    try:
        embedding = await llm_orchestrator.get_embeddings(query)
        results = journal_collection.query(
            query_embeddings=[embedding],
            n_results=limit,
        )
        if not results or not results['ids'][0]:
            return []
        entry_ids = [int(id.replace("entry_", "")) for id in results['ids'][0]]
        conn = get_db_connection()
        cursor = conn.cursor()
        entries = []
        for i, entry_id in enumerate(entry_ids):
            cursor.execute('''
            SELECT j.id, j.date, j.texte as content, j.type_entree, j.source_document, 
                   j.entreprise_id, e.nom as entreprise_nom
            FROM journal_entries j
            LEFT JOIN entreprises e ON j.entreprise_id = e.id
            WHERE j.id = ?
            ''', (entry_id,))
            entry = cursor.fetchone()
            if entry:
                entry_dict = dict(entry)
                entry_dict['similarity'] = results['distances'][0][i] if 'distances' in results else None
                cursor.execute('''
                SELECT t.nom FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ''', (entry_id,))
                entry_dict['tags'] = [row[0] for row in cursor.fetchall()]
                entries.append(entry_dict)
        conn.close()
        return entries
    except Exception as e:
        print(f"Erreur lors de la recherche: {str(e)}")
        return []

# --- Endpoints Mémoire ---
@app.post("/memoire/sections")
async def add_memoire_section(section: MemoireSection):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
    INSERT INTO memoire_sections (titre, contenu, ordre, parent_id, derniere_modification)
    VALUES (?, ?, ?, ?, ?)
    ''', (section.titre, section.contenu, section.ordre, section.parent_id, now))
    section_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"id": section_id, **section.dict()}

@app.get("/memoire/sections")
async def get_memoire_sections(parent_id: Optional[int] = None):
    conn = get_db_connection()
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
    conn.close()
    return sections

@app.get("/memoire/sections/{section_id}")
async def get_memoire_section(section_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, titre, contenu, ordre, parent_id, derniere_modification
    FROM memoire_sections
    WHERE id = ?
    ''', (section_id,))
    section = cursor.fetchone()
    if not section:
        raise HTTPException(status_code=404, detail="Section non trouvée")
    result = dict(section)
    cursor.execute('''
    SELECT j.id, j.date, j.texte as content, j.type_entree
    FROM journal_entries j
    JOIN section_entries se ON j.id = se.entry_id
    WHERE se.section_id = ?
    ''', (section_id,))
    result['journal_entries'] = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return result

@app.put("/memoire/sections/{section_id}")
async def update_memoire_section(section_id: int, section: MemoireSection):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
    UPDATE memoire_sections 
    SET titre = ?, contenu = ?, ordre = ?, parent_id = ?, derniere_modification = ?
    WHERE id = ?
    ''', (section.titre, section.contenu, section.ordre, section.parent_id, now, section_id))
    conn.commit()
    conn.close()
    return {"id": section_id, **section.dict(), "derniere_modification": now}

@app.delete("/memoire/sections/{section_id}")
async def delete_memoire_section(section_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    cursor.execute("DELETE FROM section_entries WHERE section_id = ?", (section_id,))
    cursor.execute("DELETE FROM memoire_sections WHERE id = ?", (section_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Section supprimée avec succès"}

@app.post("/memoire/sections/{section_id}/entries/{entry_id}")
async def link_entry_to_section(section_id: int, entry_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Entrée non trouvée")
    try:
        cursor.execute('''
        INSERT INTO section_entries (section_id, entry_id)
        VALUES (?, ?)
        ''', (section_id, entry_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return {"status": "success", "message": "Entrée associée à la section avec succès"}

@app.delete("/memoire/sections/{section_id}/entries/{entry_id}")
async def unlink_entry_from_section(section_id: int, entry_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    DELETE FROM section_entries
    WHERE section_id = ? AND entry_id = ?
    ''', (section_id, entry_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Association supprimée avec succès"}

# --- Endpoints IA ---
@app.post("/ai/generate-plan")
async def generate_plan(request: GeneratePlanRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT j.date, j.texte as content, j.type_entree, e.nom as entreprise
    FROM journal_entries j
    JOIN entreprises e ON j.entreprise_id = e.id
    ORDER BY j.date DESC
    LIMIT 30
    ''')
    recent_entries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    context = "Voici des extraits de mon journal de bord:\n\n"
    for entry in recent_entries:
        context += f"Date: {entry['date']}\n"
        context += f"Entreprise: {entry['entreprise']}\n"
        context += f"Type: {entry['type_entree']}\n"
        context += f"Contenu: {entry['content'][:500]}...\n\n"
    system_prompt = """Tu es un assistant spécialisé dans la création de plans de mémoire pour des étudiants en alternance. 
Tu dois créer un plan structuré pour un mémoire professionnel basé sur les extraits du journal de bord de l'étudiant.
Le plan doit suivre la structure requise pour valider le titre RNCP 35284 Expert en management des systèmes d'information."""
    user_prompt = f"{context}\n\nÀ partir de ces informations, génère un plan détaillé pour mon mémoire professionnel. {request.prompt}"
    try:
        plan_text = await llm_orchestrator.execute_task("generate", user_prompt, system_prompt)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memoire_sections")
        conn.commit()
        lines = plan_text.strip().split('\n')
        parent_id = None
        current_order = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("# ") or line.startswith("1. "):
                titre = line.split(" ", 1)[1]
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                INSERT INTO memoire_sections (titre, contenu, ordre, parent_id, derniere_modification)
                VALUES (?, ?, ?, ?, ?)
                ''', (titre, "", current_order, None, now))
                parent_id = cursor.lastrowid
                current_order += 1
            elif (line.startswith("## ") or line.startswith("1.1") or 
                  line.startswith("2.1") or line.startswith("- ")):
                if parent_id:
                    titre = line[2:] if line.startswith("- ") else (line.split(" ", 1)[1] if " " in line else line)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute('''
                    INSERT INTO memoire_sections (titre, contenu, ordre, parent_id, derniere_modification)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (titre, "", current_order, parent_id, now))
                    current_order += 1
        conn.commit()
        conn.close()
        return {"plan": plan_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du plan: {str(e)}")

@app.post("/ai/generate-content")
async def generate_content(request: GenerateContentRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, titre, parent_id, contenu
    FROM memoire_sections
    WHERE id = ?
    ''', (request.section_id,))
    section = cursor.fetchone()
    if not section:
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    section_dict = dict(section)
    parent_title = None
    if section_dict['parent_id']:
        cursor.execute('SELECT titre FROM memoire_sections WHERE id = ?', (section_dict['parent_id'],))
        parent = cursor.fetchone()
        if parent:
            parent_title = parent['titre']
    keywords = section_dict['titre'].lower().split()
    cursor.execute('''
    SELECT j.date, j.texte as content, j.type_entree, e.nom as entreprise
    FROM journal_entries j
    JOIN entreprises e ON j.entreprise_id = e.id
    ORDER BY j.date DESC
    LIMIT 10
    ''')
    all_entries = [dict(row) for row in cursor.fetchall()]
    relevant_entries = []
    for entry in all_entries:
        relevance_score = 0
        content_lower = entry["content"].lower()
        for keyword in keywords:
            if keyword in content_lower and len(keyword) > 3:
                relevance_score += 1
        if relevance_score > 0:
            entry["relevance_score"] = relevance_score
            relevant_entries.append(entry)
    relevant_entries.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    relevant_entries = relevant_entries[:5]
    conn.close()
    context = f"Je dois rédiger la section '{section_dict['titre']}'"
    if parent_title:
        context += f" de la partie '{parent_title}'"
    context += " de mon mémoire professionnel.\n\n"
    context += request.prompt if request.prompt else "Veuillez générer du contenu pour cette section en vous basant sur les entrées du journal."
    journal_content = ""
    for entry in relevant_entries[:3]:
        content_preview = entry["content"][:500] + "..." if len(entry["content"]) > 500 else entry["content"]
        journal_content += f"\n## Date: {entry['date']}\n{content_preview}\n"
    generation_prompt = f"""
# Section à rédiger
Titre: {section_dict["titre"]}
Description: {section_dict["contenu"] if len(section_dict.get("contenu", "")) < 100 else section_dict["contenu"][:100] + "..."}

# Contexte
{context}

# Entrées pertinentes du journal de bord
{journal_content if journal_content else "Aucune entrée pertinente trouvée."}

Rédigez un contenu détaillé, analytique et bien structuré pour cette section.
"""
    system_prompt = """
Vous êtes un assistant d'écriture académique pour un mémoire professionnel.
Générez du contenu détaillé, structuré et réfléchi pour la section demandée, en vous appuyant sur le contexte et les extraits du journal.
"""
    try:
        generated_content = await llm_orchestrator.execute_task("generate", generation_prompt, system_prompt)
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE memoire_sections SET contenu = ?, derniere_modification = ? WHERE id = ?",
            (generated_content, now, request.section_id)
        )
        conn.commit()
        conn.close()
        return {"generated_content": generated_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du contenu: {str(e)}")

@app.post("/ai/improve-text")
async def improve_text(request: ImproveTextRequest):
    user_prompt = request.texte
    system_prompt = f"Améliore le texte suivant en corrigeant {request.mode} et en proposant une version améliorée:" 
    try:
        improved_text = await llm_orchestrator.execute_task("improve", user_prompt, system_prompt)
        return {"improved_text": improved_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'amélioration du texte: {str(e)}")

# --- Endpoint WebSocket pour la génération en streaming ---
@app.websocket("/ws/stream_generation")
async def websocket_stream_generation(websocket: WebSocket):
    """Point d'entrée WebSocket pour la génération de texte en streaming"""
    await websocket.accept()
    
    try:
        data = await websocket.receive_text()
        params = json.loads(data)
        
        section_id = params.get("section_id")
        prompt = params.get("prompt", "")
        
        if not section_id:
            await websocket.send_json({
                "type": "error",
                "message": "section_id est requis"
            })
            return
        
        try:
            section = await memory_manager.get_section(section_id)
        except HTTPException:
            await websocket.send_json({
                "type": "error",
                "message": "Section non trouvée"
            })
            return
        
        query = prompt if prompt else section["titre"] + " " + (section["contenu"] if section["contenu"] else "")
        relevant_entries = await memory_manager.search_relevant_journal(query)
        
        outline = await memory_manager.get_outline()
        
        system_prompt = """
        Vous êtes un assistant d'écriture académique pour un mémoire professionnel.
        Générez du contenu détaillé, structuré et réfléchi pour la section demandée,
        en vous appuyant sur les informations fournies.
        """
        
        journal_content = ""
        for entry in relevant_entries[:3]:
            content_preview = entry["content"][:500] + "..." if len(entry["content"]) > 500 else entry["content"]
            journal_content += f"\n## Date: {entry['date']}\n{content_preview}\n"
        
        generation_prompt = f"""
        # Section à rédiger
        Titre: {section["titre"]}
        Description: {section["contenu"] if section["contenu"] and len(section["contenu"]) < 100 else (section["contenu"][:100] + "...")}

        # Contexte
        {prompt if prompt else "Veuillez générer du contenu pour cette section en vous basant sur les entrées du journal."}

        # Entrées pertinentes du journal de bord
        {journal_content if journal_content else "Aucune entrée pertinente trouvée."}

        Rédigez un contenu détaillé, analytique et bien structuré pour cette section.
        """
        
        await websocket.send_json({
            "type": "start",
            "message": "Génération démarrée"
        })
        
        full_content = ""
        async for text_chunk in llm_orchestrator.generate_text_streaming(generation_prompt, system_prompt):
            await websocket.send_json({
                "type": "chunk",
                "content": text_chunk
            })
            full_content += text_chunk
        
        section["contenu"] = full_content
        section["derniere_modification"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await memory_manager.save_section(section)
        
        await websocket.send_json({
            "type": "end",
            "message": "Génération terminée",
            "section_id": section_id
        })
        
    except WebSocketDisconnect:
        logger.info("Client déconnecté pendant la génération en streaming")
    except json.JSONDecodeError:
        logger.error("Format JSON invalide reçu via WebSocket")
        await websocket.send_json({
            "type": "error",
            "message": "Format de données invalide"
        })
    except Exception as e:
        logger.error(f"Erreur lors de la génération en streaming: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Erreur: {str(e)}"
            })
        except:
            pass

# --- Endpoint pour l'exécution automatique d'une tâche ---
@app.post("/ai/auto_task")
async def auto_execute_task(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "")
        system_prompt = data.get("system_prompt", None)
        if not prompt:
            raise HTTPException(status_code=400, detail="Le prompt est requis")
        result = await llm_orchestrator.execute_task("auto", prompt, system_prompt)
        return {"result": result}
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la tâche automatique: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export/{format}")
async def export_document(
    format: str,
    options: ExportOptions = Depends()
):
    if format not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail=f"Format non supporté: {format}")
    
    options.format = format
    
    exporter = MemoryExporter(memory_manager)
    
    try:
        if format == "pdf":
            document_bytes = await exporter.export_to_pdf(options)
            media_type = "application/pdf"
            filename = "memoire.pdf"
        else:
            document_bytes = await exporter.export_to_docx(options)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = "memoire.docx"
        
        return Response(
            content=document_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"Erreur lors de l'export du document: {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'export du document")

# Endpoint pour générer du contenu avec vérification des hallucinations
@app.post("/api/section/{section_id}/generate_with_verification")
async def generate_section_content_with_verification(section_id: int, request: GenerateContentRequest):
    section = await memory_manager.get_section(section_id)
    
    outline = await memory_manager.get_outline()
    
    query = request.prompt if request.prompt else section["titre"] + " " + (section["contenu"] or "")
    relevant_entries = await memory_manager.search_relevant_journal(query)
    
    generated_content = await llm_orchestrator.execute_task("generate", section["titre"], None)
    
    hallucination_detector = HallucinationDetector(memory_manager)
    context = {
        "sections": await memory_manager.search_relevant_sections(query, limit=5),
        "journal_entries": relevant_entries
    }
    verification_results = await hallucination_detector.check_content(generated_content, context)
    
    if verification_results["has_hallucinations"]:
        generated_content = verification_results["corrected_content"]
    
    section["contenu"] = generated_content
    section["derniere_modification"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await memory_manager.save_section(section)
    
    return {
        "section": section,
        "verification_results": {
            "confidence_score": verification_results["confidence_score"],
            "hallucinations_detected": verification_results["has_hallucinations"],
            "suspect_count": len(verification_results["suspect_segments"]),
            "verified_count": len(verification_results["verified_facts"])
        }
    }

@app.post("/api/backup")
async def create_backup(description: str = None):
    """
    Crée une sauvegarde complète des données du mémoire.
    """
    backup_manager = BackupManager("data")
    return await backup_manager.create_backup(description)

@app.get("/api/backup")
async def list_backups(limit: int = 20):
    """
    Liste les sauvegardes disponibles.
    """
    backup_manager = BackupManager("data")
    return await backup_manager.list_backups(limit)

@app.post("/api/backup/{backup_id}/restore")
async def restore_backup(backup_id: str):
    """
    Restaure une sauvegarde précédente.
    """
    backup_manager = BackupManager("data")
    return await backup_manager.restore_backup(backup_id)

@app.delete("/api/backup/{backup_id}")
async def delete_backup(backup_id: str):
    """
    Supprime une sauvegarde.
    """
    backup_manager = BackupManager("data")
    return await backup_manager.delete_backup(backup_id)

# ---------------------------------------------------------------------
# Endpoints de documentation améliorée (/api/...)
# ---------------------------------------------------------------------
@app.get(
    "/api/outline",
    response_model=List[Dict[str, Any]],
    tags=["Plan"],
    summary="Récupérer le plan du mémoire",
    description="Retourne la structure complète du plan du mémoire avec toutes les sections et sous-sections."
)
async def get_outline_api():
    """Récupère la structure du plan du mémoire"""
    return await memory_manager.get_outline()

@app.post(
    "/api/outline",
    response_model=List[Dict[str, Any]],
    tags=["Plan"],
    summary="Créer un plan initial",
    description="""
    Génère un plan initial pour le mémoire basé sur les entrées du journal de bord.
    Le plan généré respecte la structure attendue pour un mémoire RNCP 35284.
    """
)
async def create_initial_outline_api():
    """Crée un plan initial basé sur le journal de bord"""
    journal_entries = await memory_manager.get_journal_entries(limit=20)
    # Utilisation de llm_orchestrator pour simuler la génération initiale du plan
    outline = await llm_orchestrator.execute_task("generate_initial_outline", journal_entries)
    
    for section in outline:
        await save_section_recursive(section, memory_manager)
    
    return outline

@app.get(
    "/api/section/{section_id}",
    response_model=MemoireSection,
    tags=["Sections"],
    summary="Récupérer une section",
    description="Récupère une section du mémoire par son identifiant."
)
async def get_section_api(
    section_id: int = Path(..., description="Identifiant unique de la section")
):
    """Récupère une section par son ID"""
    return await memory_manager.get_section(section_id)

@app.post(
    "/api/section/{section_id}/generate",
    response_model=MemoireSection,
    tags=["Sections"],
    summary="Générer du contenu pour une section",
    description="""
    Génère du contenu pour une section du mémoire en utilisant l'IA.
    Le contenu est généré en tenant compte du contexte du mémoire et des entrées pertinentes du journal.
    """
)
async def generate_section_content_api(
    section_id: int = Path(..., description="Identifiant unique de la section"),
    request: GenerateRequest = Body(..., description="Paramètres pour la génération")
):
    """Génère du contenu pour une section"""
    section = await memory_manager.get_section(section_id)
    outline = await memory_manager.get_outline()
    query = request.prompt if request.prompt else section["titre"] + " " + (section["contenu"] or "")
    relevant_entries = await memory_manager.search_relevant_journal(query)
    
    # Utilisation de llm_orchestrator pour simuler la génération du contenu
    content = await llm_orchestrator.execute_task("generate_section_content", {
        "title": section["titre"],
        "content": section["contenu"],
        "relevant_entries": relevant_entries,
        "outline": outline
    })
    
    section["contenu"] = content
    section["derniere_modification"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await memory_manager.save_section(section)
    
    return section

@app.post(
    "/api/journal",
    response_model=Dict[str, Any],
    tags=["Journal"],
    summary="Ajouter une entrée au journal",
    description="""
    Ajoute une nouvelle entrée au journal de bord.
    L'entrée est indexée pour la recherche sémantique.
    """
)
async def add_journal_entry_api(
    entry: JournalEntry = Body(..., description="Entrée de journal à ajouter")
):
    """Ajoute une entrée au journal de bord"""
    return await memory_manager.add_journal_entry(entry)

@app.get(
    "/api/journal",
    response_model=List[Dict[str, Any]],
    tags=["Journal"],
    summary="Récupérer les entrées du journal",
    description="Récupère les entrées du journal de bord avec pagination."
)
async def get_journal_entries_api(
    limit: int = Query(50, description="Nombre maximum d'entrées à retourner"),
    skip: int = Query(0, description="Nombre d'entrées à sauter (pour la pagination)")
):
    """Récupère les entrées du journal de bord"""
    return await memory_manager.get_journal_entries(limit, skip)

@app.post(
    "/api/chat",
    response_model=Dict[str, Any],
    tags=["Assistant"],
    summary="Discuter avec l'assistant",
    description="""
    Envoie un message à l'assistant et récupère sa réponse.
    L'assistant utilise le contexte du mémoire et du journal pour répondre.
    """
)
async def chat_api(
    message: ChatMessage = Body(..., description="Message à envoyer à l'assistant")
):
    """Point d'API pour le chat"""
    response = await llm_orchestrator.execute_task("chat", message.message, None)
    return {"response": response}

@app.get("/health")
async def health_check():
    """
    Endpoint de vérification de santé pour les health checks
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
