import os
import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import httpx
import chromadb
from chromadb.config import Settings
import time
import uuid
import re

# Correction de l'importation du module d'extraction PDF
try:
    # Essayer d'abord l'importation standard
    from pdf_extractor import process_pdf_file
    print("Module pdf_extractor importé avec succès.")
except ImportError:
    try:
        # Si le fichier utilise un tiret et non un underscore
        import importlib.util
        import sys
        
        spec = importlib.util.spec_from_file_location("pdf_extractor", "pdf-extraction.py")
        pdf_extractor = importlib.util.module_from_spec(spec)
        sys.modules["pdf_extractor"] = pdf_extractor
        spec.loader.exec_module(pdf_extractor)
        
        from pdf_extractor import process_pdf_file
        print("Module pdf-extraction.py chargé avec succès.")
    except Exception as e:
        print(f"Erreur lors du chargement du module d'extraction PDF: {str(e)}")
        # Fonction de remplacement simple en cas d'échec de l'importation
        def process_pdf_file(file_content, filename=None):
            print("Fonction de remplacement process_pdf_file utilisée.")
            return [{"date": datetime.now().strftime("%Y-%m-%d"), 
                    "texte": "Extraction PDF non disponible. Veuillez installer les dépendances requises.", 
                    "type_entree": "quotidien", 
                    "tags": ["importation", "erreur"],
                    "source_document": filename}]

app = FastAPI()

# Définir les modèles pour la requête et la réponse
class PDFImportResponse(BaseModel):
    entries: List[dict]
    message: str

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic pour les requêtes et réponses
class JournalEntry(BaseModel):
    date: str
    texte: str
    entreprise_id: Optional[int] = None
    type_entree: Optional[str] = "quotidien"
    source_document: Optional[str] = None
    tags: Optional[List[str]] = None

class MemoireSection(BaseModel):
    titre: str
    contenu: Optional[str] = None
    ordre: int
    parent_id: Optional[int] = None

class GeneratePlanRequest(BaseModel):
    prompt: str

class GenerateContentRequest(BaseModel):
    section_id: int
    prompt: Optional[str] = None

class ImproveTextRequest(BaseModel):
    texte: str
    mode: str  # 'grammar', 'style', 'structure', etc.

# Configuration de la base de données
def get_db_connection():
    """
    Établit et retourne une connexion à la base de données SQLite
    avec gestion d'erreurs améliorée.
    """
    try:
        # S'assurer que le répertoire data existe
        os.makedirs("data", exist_ok=True)
        
        conn = sqlite3.connect("data/memoire.db")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Erreur lors de la connexion à la base de données: {e}")
        # En cas d'erreur, on peut tenter une connexion en mémoire pour éviter un crash
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        return conn

# Initialisation de la base de données
def init_db():
    """
    Initialise la base de données avec les tables nécessaires.
    Cette fonction crée les tables si elles n'existent pas déjà.
    """
    try:
        # Création du répertoire data s'il n'existe pas
        os.makedirs("data", exist_ok=True)
        
        # Connexion à la base de données
        conn = sqlite3.connect("data/memoire.db")
        cursor = conn.cursor()
        
        # Création de la table des entreprises
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entreprises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            date_debut TEXT NOT NULL,
            date_fin TEXT,
            description TEXT
        )
        ''')
        
        # Création de la table du journal de bord avec structure améliorée
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
        
        # Création d'une table pour les tags
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE
        )
        ''')
        
        # Table de relation many-to-many entre journal_entries et tags
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entry_tags (
            entry_id INTEGER,
            tag_id INTEGER,
            PRIMARY KEY (entry_id, tag_id),
            FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
        ''')
        
        # Création de la table des sections du mémoire
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

        # Création de table pour lier les entrées de journal aux sections du mémoire
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS section_entries (
            section_id INTEGER,
            entry_id INTEGER,
            PRIMARY KEY (section_id, entry_id),
            FOREIGN KEY (section_id) REFERENCES memoire_sections(id) ON DELETE CASCADE,
            FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
        )
        ''')
        
        # Vérifier si la table entreprises est vide
        cursor.execute("SELECT COUNT(*) FROM entreprises")
        if cursor.fetchone()[0] == 0:
            # Insertion des entreprises par défaut seulement si la table est vide
            cursor.execute('''
            INSERT INTO entreprises (nom, date_debut, date_fin, description)
            VALUES 
            ('AI Builders', '2023-09-01', '2024-08-31', 'Première année d''alternance'),
            ('Entreprise Actuelle', '2024-09-01', NULL, 'Deuxième année d''alternance')
            ''')
            print("Entreprises par défaut ajoutées.")
        
        # Création d'une table pour les directives et règles du mémoire
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS memoire_guidelines (
            id TEXT PRIMARY KEY,
            titre TEXT NOT NULL,
            contenu TEXT NOT NULL,
            source_document TEXT,
            created_at TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            order_index INTEGER DEFAULT 0,
            category TEXT DEFAULT 'general',
            metadata TEXT
        )
        ''')
        
        # Valider les changements
        conn.commit()
        conn.close()
        print("Base de données initialisée avec succès.")
    except Exception as e:
        print(f"Erreur lors de l'initialisation de la base de données: {str(e)}")
        # En cas d'erreur, ne pas laisser l'exception se propager pour éviter un crash

# Initialiser la base de données au démarrage
try:
    init_db()
except Exception as e:
    print(f"Erreur lors de l'initialisation de la base de données: {str(e)}")

# Configuration du client ChromaDB
try:
    chromadb_client = chromadb.Client(Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory="data/chromadb"
    ))

    # Créer la collection si elle n'existe pas déjà
    try:
        journal_collection = chromadb_client.get_collection("journal_entries")
        print("Collection ChromaDB 'journal_entries' récupérée.")
    except Exception:
        journal_collection = chromadb_client.create_collection("journal_entries")
        print("Collection ChromaDB 'journal_entries' créée.")
except Exception as e:
    print(f"Erreur lors de l'initialisation de ChromaDB: {str(e)}")
    # Objet fictif pour éviter les erreurs si ChromaDB n'est pas disponible
    class DummyCollection:
        def add(self, *args, **kwargs):
            print("ChromaDB n'est pas disponible. Opération simulée.")
            return None
        
        def query(self, *args, **kwargs):
            print("ChromaDB n'est pas disponible. Opération simulée.")
            return {"ids": [[]], "distances": [[]]}

        def update(self, *args, **kwargs):
            print("ChromaDB n'est pas disponible. Opération simulée.")
            return None
        
        def delete(self, *args, **kwargs):
            print("ChromaDB n'est pas disponible. Opération simulée.")
            return None
    
    journal_collection = DummyCollection()

# Extraction automatique de tags
def extract_automatic_tags(texte, threshold=0.01):
    """
    Extrait automatiquement des tags à partir du texte de l'entrée.
    Version simplifiée basée sur la fréquence des mots.
    
    Args:
        texte (str): Texte de l'entrée
        threshold (float): Seuil de fréquence pour considérer un mot comme tag
    
    Returns:
        list: Liste de tags potentiels
    """
    import re
    from collections import Counter
    
    # Extraction des mots (sans ponctuation, chiffres, etc.)
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', texte.lower())
    
    # Filtrer les mots vides (stopwords)
    stopwords = set(['dans', 'avec', 'pour', 'cette', 'mais', 'avoir', 'faire', 
                     'cette', 'cette', 'plus', 'tout', 'bien', 'être', 'comme', 
                     'nous', 'leur', 'sans', 'vous', 'dont'])
    words = [w for w in words if w not in stopwords]
    
    # Compter les occurrences
    word_counts = Counter(words)
    total_words = len(words)
    
    if total_words == 0:
        return []
    
    # Sélectionner les mots qui dépassent le seuil
    potential_tags = [word for word, count in word_counts.items() 
                    if count / total_words > threshold]
    
    return potential_tags[:5]  # Limiter à 5 tags maximum

# Ajouter ces routes à votre fichier main.py
@app.post("/import/pdf", response_model=PDFImportResponse)
async def import_pdf(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
):
    """
    Importe un fichier PDF et extrait son contenu sous forme d'entrées de journal.
    
    Args:
        file: Le fichier PDF à traiter
        entreprise_id: ID de l'entreprise associée aux entrées (optionnel)
        
    Returns:
        PDFImportResponse: Les entrées extraites et un message de succès
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le PDF
        entries = process_pdf_file(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        
        # Ajouter entreprise_id si fourni
        if entreprise_id is not None:
            for entry in entries:
                entry["entreprise_id"] = entreprise_id
        
        # Ajouter les entrées à la base de données
        added_entries = []
        for entry in entries:
            result = add_journal_entry(entry)
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
    """
    Analyse un fichier PDF sans l'importer dans la base de données.
    Utile pour prévisualiser les entrées qui seraient créées.
    
    Args:
        file: Le fichier PDF à analyser
        
    Returns:
        List[dict]: Les entrées extraites
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le PDF
        entries = process_pdf_file(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail="Impossible d'extraire des entrées du PDF.")
        
        return entries
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du PDF: {str(e)}")

# Routes API pour le journal de bord
@app.post("/journal/entries")
async def add_journal_entry(entry: JournalEntry):
    """Ajoute une entrée au journal de bord"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Si entreprise_id est None, déterminer automatiquement en fonction de la date
    entreprise_id = entry.entreprise_id
    if entreprise_id is None:
        cursor.execute('''
        SELECT id FROM entreprises 
        WHERE date_debut <= ? AND (date_fin IS NULL OR date_fin >= ?)
        ''', (entry.date, entry.date))
        result = cursor.fetchone()
        if result:
            entreprise_id = result[0]
    
    # Génération automatique de tags si non fournis
    tags = entry.tags
    if not tags:
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
            # Récupérer ou créer le tag
            cursor.execute("SELECT id FROM tags WHERE nom = ?", (tag,))
            result = cursor.fetchone()
            
            if result:
                tag_id = result[0]
            else:
                cursor.execute("INSERT INTO tags (nom) VALUES (?)", (tag,))
                tag_id = cursor.lastrowid
            
            # Associer le tag à l'entrée
            cursor.execute("INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", 
                          (entry_id, tag_id))
    
    conn.commit()
    
    # Ajouter l'entrée à la base de données vectorielle
    try:
        journal_collection.add(
            documents=[entry.texte],
            metadatas=[{"date": entry.date, "entry_id": entry_id}],
            ids=[f"entry_{entry_id}"]
        )
    except Exception as e:
        print(f"Erreur lors de l'ajout à ChromaDB: {str(e)}")
    
    # Récupérer l'entrée complète pour la renvoyer
    cursor.execute('''
    SELECT j.id, j.date, j.texte, j.type_entree, j.source_document, j.entreprise_id,
           e.nom as entreprise_nom
    FROM journal_entries j
    LEFT JOIN entreprises e ON j.entreprise_id = e.id
    WHERE j.id = ?
    ''', (entry_id,))
    
    inserted_entry = dict(cursor.fetchone())
    
    # Récupérer les tags associés
    cursor.execute('''
    SELECT t.nom FROM tags t
    JOIN entry_tags et ON t.id = et.tag_id
    WHERE et.entry_id = ?
    ''', (entry_id,))
    
    inserted_entry['tags'] = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return inserted_entry

@app.get("/journal/entries")
async def get_journal_entries(start_date: Optional[str] = None, 
                             end_date: Optional[str] = None,
                             entreprise_id: Optional[int] = None,
                             type_entree: Optional[str] = None,
                             tag: Optional[str] = None):
    """Récupère les entrées du journal avec filtres optionnels"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
    SELECT DISTINCT j.id, j.date, j.texte, j.type_entree, j.source_document, 
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
    
    query += " ORDER BY j.date DESC"
    
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
    
    conn.close()
    return entries

@app.get("/journal/entries/{entry_id}")
async def get_journal_entry(entry_id: int):
    """Récupère une entrée spécifique du journal"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT j.id, j.date, j.texte, j.type_entree, j.source_document, 
           j.entreprise_id, e.nom as entreprise_nom
    FROM journal_entries j
    LEFT JOIN entreprises e ON j.entreprise_id = e.id
    WHERE j.id = ?
    ''', (entry_id,))
    
    entry = cursor.fetchone()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrée non trouvée")
    
    result = dict(entry)
    
    # Récupérer les tags associés
    cursor.execute('''
    SELECT t.nom FROM tags t
    JOIN entry_tags et ON t.id = et.tag_id
    WHERE et.entry_id = ?
    ''', (entry_id,))
    
    result['tags'] = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return result

@app.put("/journal/entries/{entry_id}")
async def update_journal_entry(entry_id: int, entry: JournalEntry):
    """Met à jour une entrée existante du journal"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier si l'entrée existe
    cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Entrée non trouvée")
    
    # Mise à jour de l'entrée
    cursor.execute('''
    UPDATE journal_entries 
    SET date = ?, texte = ?, entreprise_id = ?, type_entree = ?, source_document = ?
    WHERE id = ?
    ''', (entry.date, entry.texte, entry.entreprise_id, entry.type_entree, 
          entry.source_document, entry_id))
    
    # Supprimer les anciens tags
    cursor.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
    
    # Ajouter les nouveaux tags
    if entry.tags:
        for tag in entry.tags:
            # Récupérer ou créer le tag
            cursor.execute("SELECT id FROM tags WHERE nom = ?", (tag,))
            result = cursor.fetchone()
            
            if result:
                tag_id = result[0]
            else:
                cursor.execute("INSERT INTO tags (nom) VALUES (?)", (tag,))
                tag_id = cursor.lastrowid
            
            # Associer le tag à l'entrée
            cursor.execute("INSERT INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", 
                          (entry_id, tag_id))
    
    conn.commit()
    
    # Mettre à jour l'entrée dans la base de données vectorielle
    try:
        journal_collection.update(
            documents=[entry.texte],
            metadatas=[{"date": entry.date, "entry_id": entry_id}],
            ids=[f"entry_{entry_id}"]
        )
    except Exception as e:
        print(f"Erreur lors de la mise à jour dans ChromaDB: {str(e)}")
    
    # Récupérer l'entrée mise à jour pour la renvoyer
    cursor.execute('''
    SELECT j.id, j.date, j.texte, j.type_entree, j.source_document, 
           j.entreprise_id, e.nom as entreprise_nom
    FROM journal_entries j
    LEFT JOIN entreprises e ON j.entreprise_id = e.id
    WHERE j.id = ?
    ''', (entry_id,))
    
    updated_entry = dict(cursor.fetchone())
    
    # Récupérer les tags associés
    cursor.execute('''
    SELECT t.nom FROM tags t
    JOIN entry_tags et ON t.id = et.tag_id
    WHERE et.entry_id = ?
    ''', (entry_id,))
    
    updated_entry['tags'] = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return updated_entry

@app.delete("/journal/entries/{entry_id}")
async def delete_journal_entry(entry_id: int):
    """Supprime une entrée du journal"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier si l'entrée existe
    cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Entrée non trouvée")
    
    # Supprimer l'entrée (les tags associés seront supprimés automatiquement grâce à ON DELETE CASCADE)
    cursor.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    
    # Supprimer l'entrée de la base de données vectorielle
    try:
        journal_collection.delete(ids=[f"entry_{entry_id}"])
    except Exception as e:
        print(f"Erreur lors de la suppression dans ChromaDB: {str(e)}")
    
    return {"status": "success", "message": "Entrée supprimée avec succès"}

@app.get("/entreprises")
async def get_entreprises():
    """Récupère la liste des entreprises"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, nom, date_debut, date_fin, description FROM entreprises")
    entreprises = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return entreprises

@app.get("/tags")
async def get_tags():
    """Récupère la liste des tags avec leur fréquence"""
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

# Routes API pour la recherche
@app.get("/search")
async def search_entries(query: str, limit: int = 5):
    """Recherche des entrées de journal basée sur la similarité sémantique"""
    try:
        results = journal_collection.query(
            query_texts=[query],
            n_results=limit,
        )
        
        if not results or not results['ids'][0]:
            return []
        
        # Récupérer les détails complets des entrées trouvées
        entry_ids = [int(id.replace("entry_", "")) for id in results['ids'][0]]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        entries = []
        for i, entry_id in enumerate(entry_ids):
            cursor.execute('''
            SELECT j.id, j.date, j.texte, j.type_entree, j.source_document, 
                   j.entreprise_id, e.nom as entreprise_nom
            FROM journal_entries j
            LEFT JOIN entreprises e ON j.entreprise_id = e.id
            WHERE j.id = ?
            ''', (entry_id,))
            
            entry = cursor.fetchone()
            if entry:
                entry_dict = dict(entry)
                
                # Ajouter le score de similarité
                entry_dict['similarity'] = results['distances'][0][i] if 'distances' in results else None
                
                # Récupérer les tags
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

# Routes API pour le mémoire
@app.post("/memoire/sections")
async def add_memoire_section(section: MemoireSection):
    """Ajoute une section au mémoire"""
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
    """Récupère les sections du mémoire"""
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
    """Récupère une section spécifique du mémoire"""
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
    
    # Récupérer les entrées de journal associées
    cursor.execute('''
    SELECT j.id, j.date, j.texte, j.type_entree
    FROM journal_entries j
    JOIN section_entries se ON j.id = se.entry_id
    WHERE se.section_id = ?
    ''', (section_id,))
    
    result['journal_entries'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return result

@app.put("/memoire/sections/{section_id}")
async def update_memoire_section(section_id: int, section: MemoireSection):
    """Met à jour une section du mémoire"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier si la section existe
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
    """Supprime une section du mémoire"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier si la section existe
    cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    
    # Supprimer les associations avec les entrées de journal
    cursor.execute("DELETE FROM section_entries WHERE section_id = ?", (section_id,))
    
    # Supprimer la section
    cursor.execute("DELETE FROM memoire_sections WHERE id = ?", (section_id,))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Section supprimée avec succès"}

@app.post("/memoire/sections/{section_id}/entries/{entry_id}")
async def link_entry_to_section(section_id: int, entry_id: int):
    """Associe une entrée de journal à une section du mémoire"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier si la section existe
    cursor.execute("SELECT id FROM memoire_sections WHERE id = ?", (section_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    
    # Vérifier si l'entrée existe
    cursor.execute("SELECT id FROM journal_entries WHERE id = ?", (entry_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Entrée non trouvée")
    
    # Associer l'entrée à la section
    try:
        cursor.execute('''
        INSERT INTO section_entries (section_id, entry_id)
        VALUES (?, ?)
        ''', (section_id, entry_id))
        conn.commit()
    except sqlite3.IntegrityError:
        # Si l'association existe déjà, ignorer l'erreur
        pass
    
    conn.close()
    return {"status": "success", "message": "Entrée associée à la section avec succès"}

@app.delete("/memoire/sections/{section_id}/entries/{entry_id}")
async def unlink_entry_from_section(section_id: int, entry_id: int):
    """Supprime l'association entre une entrée de journal et une section du mémoire"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    DELETE FROM section_entries
    WHERE section_id = ? AND entry_id = ?
    ''', (section_id, entry_id))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Association supprimée avec succès"}

# Routes pour l'IA
# Fonction pour communiquer avec le modèle Ollama
async def query_ollama(prompt, system=None, model="llama3"):
    """
    Envoie une requête au modèle Ollama et retourne la réponse.
    Gère les erreurs et les délais d'attente.
    """
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    if system:
        payload["system"] = system
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{ollama_url}/api/generate", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"Erreur HTTP lors de la communication avec Ollama: {e}")
        return {"response": f"Erreur de communication avec le modèle: {str(e)}"}
    except httpx.RequestError as e:
        print(f"Erreur de requête lors de la communication avec Ollama: {e}")
        return {"response": "Le service Ollama n'est pas disponible. Veuillez vérifier que le service est en cours d'exécution."}
    except Exception as e:
        print(f"Erreur inattendue lors de la communication avec Ollama: {e}")
        return {"response": f"Une erreur s'est produite: {str(e)}"}

@app.post("/ai/generate-plan")
async def generate_plan(request: GeneratePlanRequest):
    """Génère un plan de mémoire basé sur le journal de bord"""
    # Récupérer les entrées récentes du journal
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT j.date, j.texte, j.type_entree, e.nom as entreprise
    FROM journal_entries j
    JOIN entreprises e ON j.entreprise_id = e.id
    ORDER BY j.date DESC
    LIMIT 30
    ''')
    
    recent_entries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Construire le contexte pour le modèle
    context = "Voici des extraits de mon journal de bord:\n\n"
    for entry in recent_entries:
        context += f"Date: {entry['date']}\n"
        context += f"Entreprise: {entry['entreprise']}\n"
        context += f"Type: {entry['type_entree']}\n"
        context += f"Contenu: {entry['texte'][:500]}...\n\n"
    
    # Construire le prompt
    system_prompt = """Tu es un assistant spécialisé dans la création de plans de mémoire pour des étudiants en alternance. 
    Tu dois créer un plan structuré pour un mémoire professionnel basé sur les extraits du journal de bord de l'étudiant.
    Le plan doit suivre la structure requise pour valider le titre RNCP 35284 Expert en management des systèmes d'information."""
    
    user_prompt = f"{context}\n\nÀ partir de ces informations, génère un plan détaillé pour mon mémoire professionnel. {request.prompt}"
    
    # Appeler le modèle
    try:
        response = await query_ollama(user_prompt, system=system_prompt)
        plan_text = response.get('response', '')
        
        # Créer les sections dans la base de données
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Supprimer les sections existantes
        cursor.execute("DELETE FROM memoire_sections")
        conn.commit()
        
        # Analyser le plan généré pour extraire les sections
        lines = plan_text.strip().split('\n')
        parent_id = None
        current_order = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Détecter les titres de premier niveau
            if line.startswith("# ") or line.startswith("1. "):
                titre = line.split(" ", 1)[1]
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute('''
                INSERT INTO memoire_sections (titre, contenu, ordre, parent_id, derniere_modification)
                VALUES (?, ?, ?, ?, ?)
                ''', (titre, "", current_order, None, now))
                
                parent_id = cursor.lastrowid
                current_order += 1
            
            # Détecter les titres de second niveau
            elif (line.startswith("## ") or line.startswith("1.1") or 
                  line.startswith("2.1") or line.startswith("- ")):
                if parent_id:
                    if line.startswith("- "):
                        titre = line[2:]
                    else:
                        titre = line.split(" ", 1)[1] if " " in line else line
                    
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
    """Génère du contenu pour une section du mémoire basé sur le journal de bord"""
    # Récupérer la section
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT id, titre, parent_id
    FROM memoire_sections
    WHERE id = ?
    ''', (request.section_id,))
    
    section = cursor.fetchone()
    if not section:
        conn.close()
        raise HTTPException(status_code=404, detail="Section non trouvée")
    
    section_dict = dict(section)
    
    # Récupérer le parent si existant
    parent_title = None
    if section_dict['parent_id']:
        cursor.execute('''
        SELECT titre
        FROM memoire_sections
        WHERE id = ?
        ''', (section_dict['parent_id'],))
        
        parent = cursor.fetchone()
        if parent:
            parent_title = parent['titre']
    
    # Rechercher des entrées pertinentes dans le journal
    # Comme ChromaDB pourrait ne pas être disponible, recherche basique par mots-clés
    keywords = section_dict['titre'].lower().split()
    cursor.execute('''
    SELECT j.date, j.texte, j.type_entree, e.nom as entreprise
    FROM journal_entries j
    JOIN entreprises e ON j.entreprise_id = e.id
    ORDER BY j.date DESC
    LIMIT 10
    ''')
    
    all_entries = [dict(row) for row in cursor.fetchall()]
    relevant_entries = []
    
    for entry in all_entries:
        relevance_score = 0
        content_lower = entry["texte"].lower()
        
        for keyword in keywords:
            if keyword in content_lower and len(keyword) > 3:
                relevance_score += 1
        
        if relevance_score > 0:
            entry["relevance_score"] = relevance_score
            relevant_entries.append(entry)
    
    # Trier par pertinence
    relevant_entries.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    relevant_entries = relevant_entries[:5]  # Limiter aux 5 plus pertinentes
    
    conn.close()
    
    # Construire le contexte pour le modèle
    context = f"Je dois rédiger la section '{section_dict['titre']}'"
    if parent_title:
        context += f" de la partie '{parent_title}'"
    context += " de mon mémoire professionnel.\n\n"
    
    context += "Voici des extraits pertinents de mon journal de bord:\n\n"
    for entry in relevant_entries:
        content_preview = entry["texte"][:500] + "..." if len(entry["texte"]) > 500 else entry["texte"]
        context += f"Date: {entry['date']}\n"
        context += f"Entreprise: {entry['entreprise']}\n"
        context += f"Type: {entry['type_entree']}\n"
        context += f"Contenu: {content_preview}\n\n"
    
    # Construire le prompt
    system_prompt = """Tu es un assistant spécialisé dans la rédaction de mémoires professionnels. 
    Tu dois générer un contenu professionnel, bien structuré et détaillé pour une section de mémoire d'alternance.
    Le contenu doit être basé sur les extraits du journal de bord fournis et adapté au titre de la section."""
    
    user_prompt = f"{context}\n\nÀ partir de ces informations, rédige un contenu détaillé et professionnel pour cette section."
    if request.prompt:
        user_prompt += f" {request.prompt}"
    
    # Appeler le modèle
    try:
        response = await query_ollama(user_prompt, system=system_prompt)
        generated_content = response.get('response', '')
        
        # Mettre à jour la section avec le contenu généré
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
        UPDATE memoire_sections 
        SET contenu = ?, derniere_modification = ?
        WHERE id = ?
        ''', (generated_content, now, request.section_id))
        
        conn.commit()
        conn.close()
        
        return {"content": generated_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du contenu: {str(e)}")

@app.post("/ai/improve-text")
async def improve_text(request: ImproveTextRequest):
    """Améliore un texte selon différents modes (grammaire, style, structure)"""
    system_prompts = {
        "grammar": "Tu es un correcteur orthographique et grammatical expert. Corrige les erreurs dans le texte fourni tout en préservant son sens et sa structure.",
        "style": "Tu es un expert en rédaction académique. Améliore le style d'écriture du texte fourni pour le rendre plus professionnel et adapté à un mémoire d'alternance.",
        "structure": "Tu es un expert en structuration de texte. Réorganise et structure le texte fourni pour améliorer sa clarté et sa cohérence.",
        "expand": "Tu es un expert en rédaction. Développe et enrichis le texte fourni avec plus de détails et d'exemples pertinents."
    }
    
    mode = request.mode.lower()
    if mode not in system_prompts:
        raise HTTPException(status_code=400, detail=f"Mode non reconnu: {mode}")
    
    system_prompt = system_prompts[mode]
    user_prompt = f"Voici le texte à améliorer :\n\n{request.texte}"
    
    try:
        response = await query_ollama(user_prompt, system=system_prompt)
        improved_text = response.get('response', '')
        
        return {"improved_text": improved_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'amélioration du texte: {str(e)}")

# Ajout d'une route pour importer des documents
@app.post("/import/document")
async def import_document(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
):
    """
    Importe un fichier (PDF ou DOCX) et extrait son contenu sous forme d'entrées de journal
    
    Cette fonction permet d'analyser un document et d'en extraire automatiquement des entrées de journal.
    """
    # Vérifier l'extension mais permettre les types MIME
    filename = file.filename
    filename_lower = filename.lower()
    is_valid = (
        filename_lower.endswith('.pdf') or 
        filename_lower.endswith('.docx') or
        'pdf' in filename_lower or
        'docx' in filename_lower or
        file.content_type in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    )
    
    # Logging pour le débogage des problèmes de date
    print(f"[DATE_DEBUG] Nom original du fichier pour extraction de date: {filename}")
    
    # Tenter d'extraire la date directement depuis le nom de fichier
    from utils.pdf_extractor import extract_date_from_filename
    file_date = extract_date_from_filename(filename)
    if file_date:
        print(f"[DATE_DEBUG] Date extraite du nom de fichier: {file_date}")
    
    if not is_valid:
        print(f"Type de fichier non pris en charge: {file.filename} ({file.content_type})")
        # Au lieu de rejeter, créer une entrée artificielle
        current_date = datetime.now().strftime("%Y-%m-%d")
        entry_obj = {
            "date": current_date,
            "texte": f"Fichier {file.filename} importé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}. Type de fichier non reconnu.",
            "type_entree": "quotidien",
            "source_document": file.filename,
            "tags": ["projet", "document"]
        }
        
        try:
            inserted_entry = await add_journal_entry(JournalEntry(**entry_obj))
            return {
                "entries": [inserted_entry],
                "message": "Import de secours réalisé pour un fichier de type non reconnu."
            }
        except Exception as e:
            print(f"Erreur lors de la création de l'entrée de secours: {str(e)}")
            raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF ou DOCX.")
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le document
        entries = process_pdf_file(contents, file.filename)
        
        # Si l'extraction a échoué mais qu'une date a été extraite du nom de fichier, créer une entrée de secours
        if not entries and file_date:
            print(f"[DATE_DEBUG] Création d'une entrée de secours avec la date extraite du nom de fichier: {file_date}")
            entries = [{
                "date": file_date,
                "texte": f"Document {file.filename} importé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.\n\nLe contenu n'a pas pu être extrait correctement.",
                "type_entree": "quotidien",
                "tags": ["projet", "document"],
                "source_document": file.filename,
                "date_source": "filename"
            }]
        elif not entries:
            raise HTTPException(status_code=400, detail=f"Impossible d'extraire des entrées du document {file.filename}.")
        
        # Validation des entrées avant traitement
        valid_entries = []
        for entry in entries:
            # Si l'entrée n'a pas de date définie mais que nous avons extrait une date du nom de fichier
            if ("date" not in entry or not entry["date"]) and file_date:
                print(f"[DATE_DEBUG] Utilisation de la date extraite du nom de fichier pour une entrée sans date")
                entry["date"] = file_date
                entry["date_source"] = "filename"
            
            # Vérifier que le texte a la longueur minimale requise
            if "texte" in entry and len(entry["texte"]) < 10:
                print(f"[DATE_DEBUG] Entrée avec texte trop court ({len(entry['texte'])} caractères) - ajout de contenu")
                # Ajouter du contenu pour atteindre la longueur minimale
                entry["texte"] = entry["texte"] + "\n\n" + f"Note générée le {datetime.now().strftime('%d/%m/%Y')} à partir du document {file.filename}"
            
            # Vérifier à nouveau et s'assurer que toutes les propriétés requises sont présentes
            if "texte" in entry and "date" in entry and len(entry["texte"]) >= 10:
                valid_entries.append(entry)
            else:
                print(f"[DATE_DEBUG] Entrée invalide ignorée: {entry}")
        
        if not valid_entries:
            # Si aucune entrée valide mais nous avons une date du nom de fichier
            if file_date:
                print(f"[DATE_DEBUG] Création d'une entrée de secours avec la date du nom de fichier: {file_date}")
                valid_entries = [{
                    "date": file_date,
                    "texte": f"Document {file.filename} importé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.\n\nLe contenu n'a pas pu être extrait correctement.",
                    "type_entree": "quotidien",
                    "tags": ["import", "erreur"],
                    "source_document": file.filename,
                    "date_source": "filename"
                }]
            else:
                raise HTTPException(status_code=400, detail=f"Aucune entrée valide extraite du document {file.filename}.")
        
        entries = valid_entries
        print(f"{len(entries)} entrées valides extraites du document")
        
        # Ajouter entreprise_id si fourni
        if entreprise_id is not None:
            for entry in entries:
                entry["entreprise_id"] = entreprise_id
        
        # Ajouter les entrées à la base de données
        added_entries = []
        for entry_data in entries:
            # Convertir la date string en objet datetime si nécessaire
            if isinstance(entry_data.get("date"), str):
                try:
                    # Convertir le format YYYY-MM-DD en objet datetime
                    entry_data["date"] = datetime.strptime(entry_data["date"], "%Y-%m-%d")
                    # Marquer cette entrée comme ayant une date provenant du nom de fichier pour traçabilité
                    if entry_data.get("date_source") == "filename":
                        print(f"[DATE_PRIORITY] Date du nom de fichier maintenue pour l'entrée: {entry_data['date'].strftime('%Y-%m-%d')}")
                        if "tags" not in entry_data:
                            entry_data["tags"] = []
                        if "date_from_filename" not in entry_data["tags"]:
                            entry_data["tags"].append("date_from_filename")
                except ValueError as e:
                    print(f"Erreur de conversion de date: {e}")
                    continue  # Ignorer cette entrée et passer à la suivante
            
            # Débogage de la date extraite
            date_source = entry_data.get("date_source", "unknown")
            date_value = entry_data["date"].strftime("%Y-%m-%d") if isinstance(entry_data["date"], datetime) else entry_data["date"]
            print(f"[DATE_DEBUG] Entrée avec date {date_value} (source: {date_source})")
            
            # Créer un objet JournalEntry à partir des données
            entry_obj = {
                "date": date_value,
                "texte": entry_data["texte"],
                "type_entree": entry_data.get("type_entree", "quotidien"),
                "entreprise_id": entry_data.get("entreprise_id"),
                "source_document": file.filename,
                "tags": entry_data.get("tags", [])
            }
            
            # Ajouter l'entrée via la fonction API existante
            try:
                inserted_entry = await add_journal_entry(JournalEntry(**entry_obj))
                if inserted_entry:
                    added_entries.append(inserted_entry)
            except Exception as e:
                print(f"Erreur lors de l'ajout d'une entrée: {str(e)}")
        
        return {
            "entries": added_entries,
            "message": f"{len(added_entries)} entrées ajoutées avec succès."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur lors du traitement du document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du document: {str(e)}")

# Ajout d'une route pour analyser sans importer
@app.post("/import/document/analyze")
async def analyze_document_without_import(
    file: UploadFile = File(...),
):
    """
    Analyse un fichier (PDF ou DOCX) sans l'importer dans la base de données
    
    Cette fonction permet de prévisualiser les entrées qui seraient créées à partir d'un document.
    """
    # Vérifier l'extension mais permettre les types MIME
    filename = file.filename.lower()
    is_valid = (
        filename.endswith('.pdf') or 
        filename.endswith('.docx') or
        'pdf' in filename or
        'docx' in filename or
        file.content_type in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    )
    
    if not is_valid:
        print(f"Type de fichier non pris en charge pour l'analyse: {file.filename} ({file.content_type})")
        # Plutôt que de rejeter le fichier, renvoyer une entrée d'erreur
        current_date = datetime.now().strftime("%Y-%m-%d")
        return [{
            "date": current_date,
            "texte": f"Le fichier {file.filename} n'a pas pu être analysé. Seuls les fichiers PDF et DOCX sont pris en charge.",
            "type_entree": "erreur",
            "tags": ["projet", "document"],
            "source_document": file.filename
        }]
    
    try:
        # Lire le contenu du fichier
        contents = await file.read()
        
        # Traiter le document
        entries = process_pdf_file(contents, file.filename)
        
        if not entries:
            raise HTTPException(status_code=400, detail=f"Impossible d'extraire des entrées du document {file.filename}.")
        
        # Validation des entrées avant traitement
        valid_entries = []
        for entry in entries:
            # Vérifier que le texte a la longueur minimale requise
            if "texte" in entry and len(entry["texte"]) < 10:
                print(f"Entrée avec texte trop court ({len(entry['texte'])} caractères) - texte complété")
                # Ajouter du contenu pour atteindre la longueur minimale
                entry["texte"] = entry["texte"] + "\n\n" + f"Note analysée le {datetime.now().strftime('%d/%m/%Y')} - Document: {file.filename}"
            
            # S'assurer que toutes les propriétés requises sont présentes
            if "texte" in entry and "date" in entry and len(entry["texte"]) >= 10:
                valid_entries.append(entry)
            else:
                print(f"Entrée invalide ignorée lors de l'analyse: {entry}")
        
        if not valid_entries:
            raise HTTPException(status_code=400, detail=f"Aucune entrée valide extraite du document {file.filename} lors de l'analyse.")
        
        entries = valid_entries
        
        # Pour chaque entrée, convertir la date au format ISO pour éviter des problèmes de sérialisation
        for entry in entries:
            if isinstance(entry.get("date"), str):
                try:
                    # Pour l'API, on peut laisser la date sous forme de string, mais au format ISO
                    date_obj = datetime.strptime(entry["date"], "%Y-%m-%d")
                    entry["date"] = date_obj.isoformat()
                except ValueError:
                    pass  # Garder la date dans son format original si la conversion échoue
        
        return entries
        
    except Exception as e:
        print(f"Erreur lors de l'analyse du document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'analyse du document: {str(e)}")

# Ajout des mêmes routes avec le préfixe /journal pour compatibilité
@app.post("/journal/import/document")
async def journal_import_document(
    file: UploadFile = File(...),
    entreprise_id: Optional[int] = Form(None),
):
    """
    Importe un fichier (PDF ou DOCX) et extrait son contenu sous forme d'entrées de journal (avec préfixe journal)
    """
    # Logging pour le débogage des dates
    print(f"[DATE_DEBUG] Import via /journal/import/document: {file.filename}")
    try:
        return await import_document(file, entreprise_id)
    except Exception as e:
        print(f"Erreur lors de l'import via la route /journal/: {str(e)}")
        # Créer une entrée de secours en cas d'erreur
        current_date = datetime.now().strftime("%Y-%m-%d")
        entry_obj = {
            "date": current_date,
            "texte": f"Fichier {file.filename} importé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}. Une erreur s'est produite: {str(e)}",
            "type_entree": "quotidien",
            "source_document": file.filename,
            "tags": ["import", "erreur"]
        }
        
        try:
            inserted_entry = await add_journal_entry(JournalEntry(**entry_obj))
            return {
                "entries": [inserted_entry],
                "message": "Import de secours réalisé suite à une erreur."
            }
        except Exception as inner_e:
            print(f"Erreur lors de la création de l'entrée de secours: {str(inner_e)}")
            # Même en cas d'erreur, renvoyer une réponse pour éviter le 500
            return {
                "entries": [],
                "message": f"Erreur lors de l'import: {str(e)}"
            }

@app.post("/journal/import/document/analyze")
async def journal_analyze_document(
    file: UploadFile = File(...),
):
    """
    Analyse un fichier (PDF ou DOCX) sans l'importer dans la base de données (avec préfixe journal)
    """
    # Logging pour le débogage des dates
    print(f"[DATE_DEBUG] Analyse via /journal/import/document/analyze: {file.filename}")
    try:
        return await analyze_document_without_import(file)
    except Exception as e:
        print(f"Erreur lors de l'analyse du document via la route /journal/: {str(e)}")
        # En cas d'erreur, retourner une entrée par défaut pour éviter l'échec
        current_date = datetime.now().strftime("%Y-%m-%d")
        return [{
            "date": current_date,
            "texte": f"Le fichier {file.filename} n'a pas pu être analysé en raison d'une erreur: {str(e)}",
            "type_entree": "erreur",
            "tags": ["erreur", "import"],
            "source_document": file.filename
        }]

# Ajout d'une route pour récupérer les sources d'import
@app.get("/journal/import/sources")
async def get_import_sources():
    """
    Liste tous les documents sources utilisés pour les imports
    
    Cette fonction permet de récupérer la liste des noms de fichiers ayant servi à des imports.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT source_document, COUNT(*) as entry_count, MIN(date) as first_date, MAX(date) as last_date
        FROM journal_entries
        WHERE source_document IS NOT NULL AND source_document != ''
        GROUP BY source_document
        ORDER BY last_date DESC
        """)
        
        sources = []
        for row in cursor.fetchall():
            source_dict = dict(row)
            
            # Ajouter la taille totale de texte
            cursor.execute("""
            SELECT SUM(LENGTH(texte)) as total_text_size
            FROM journal_entries
            WHERE source_document = ?
            """, (source_dict['source_document'],))
            
            size_row = cursor.fetchone()
            source_dict['total_text_size'] = size_row['total_text_size'] if size_row else 0
            
            sources.append(source_dict)
        
        conn.close()
        return sources
        
    except Exception as e:
        print(f"Erreur lors de la récupération des sources d'import: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Ajout d'une route pour nettoyer tous les imports
@app.delete("/journal/import/cleanup")
async def cleanup_all_imports():
    """
    Supprime toutes les entrées de journal créées à partir de documents importés
    
    Cette fonction permet de nettoyer la base de données des entrées générées automatiquement.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer les IDs des entrées à supprimer
        cursor.execute("""
        SELECT id FROM journal_entries 
        WHERE source_document IS NOT NULL AND source_document != ''
        """)
        
        entries_to_delete = [row['id'] for row in cursor.fetchall()]
        
        if not entries_to_delete:
            return {"status": "success", "message": "Aucune entrée issue d'imports à supprimer", "deleted_count": 0}
        
        # Récupérer les tags associés à ces entrées pour identifier les tags potentiellement orphelins
        cursor.execute("""
        SELECT DISTINCT et.tag_id 
        FROM entry_tags et
        WHERE et.entry_id IN (""" + ",".join("?" for _ in entries_to_delete) + ")",
        entries_to_delete)
        
        tags_to_check = [row[0] for row in cursor.fetchall()]
        
        # Pour chaque entrée, supprimer de ChromaDB
        for entry_id in entries_to_delete:
            try:
                journal_collection.delete(ids=[f"entry_{entry_id}"])
            except Exception as e:
                print(f"Erreur lors de la suppression dans ChromaDB (ID {entry_id}): {str(e)}")
        
        # Supprimer les entrées de la base SQLite
        cursor.execute("""
        DELETE FROM journal_entries 
        WHERE source_document IS NOT NULL AND source_document != ''
        """)
        
        deleted_count = cursor.rowcount
        
        # Supprimer les tags devenus orphelins (associés uniquement aux entrées importées)
        for tag_id in tags_to_check:
            # Vérifier si ce tag est encore utilisé
            cursor.execute("""
            SELECT COUNT(*) FROM entry_tags WHERE tag_id = ?
            """, (tag_id,))
            
            tag_usage_count = cursor.fetchone()[0]
            
            if tag_usage_count == 0:
                # Récupérer le nom du tag pour le log
                cursor.execute("SELECT nom FROM tags WHERE id = ?", (tag_id,))
                tag_row = cursor.fetchone()
                tag_name = tag_row[0] if tag_row else f"ID {tag_id}"
                
                # Si le tag n'est plus utilisé, le supprimer
                cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
                print(f"Tag orphelin '{tag_name}' supprimé")
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success", 
            "message": f"{deleted_count} entrées issues d'imports supprimées",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        print(f"Erreur lors du nettoyage des imports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Ajout d'une route pour nettoyer un import spécifique
@app.delete("/journal/import/document/{filename}")
async def cleanup_document_import(filename: str):
    """
    Supprime les entrées de journal créées à partir d'un document spécifique
    
    Cette fonction permet de nettoyer la base de données des entrées issues d'un import particulier.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer les IDs des entrées à supprimer
        cursor.execute("""
        SELECT id FROM journal_entries 
        WHERE source_document = ?
        """, (filename,))
        
        entries_to_delete = [row['id'] for row in cursor.fetchall()]
        
        if not entries_to_delete:
            raise HTTPException(status_code=404, detail=f"Aucune entrée trouvée pour le document {filename}")
        
        # Récupérer les tags associés à ces entrées pour identifier les tags potentiellement orphelins
        cursor.execute("""
        SELECT DISTINCT et.tag_id 
        FROM entry_tags et
        WHERE et.entry_id IN (""" + ",".join("?" for _ in entries_to_delete) + ")",
        entries_to_delete)
        
        tags_to_check = [row[0] for row in cursor.fetchall()]
        
        # Pour chaque entrée, supprimer de ChromaDB
        for entry_id in entries_to_delete:
            try:
                journal_collection.delete(ids=[f"entry_{entry_id}"])
            except Exception as e:
                print(f"Erreur lors de la suppression dans ChromaDB (ID {entry_id}): {str(e)}")
        
        # Supprimer les entrées de la base SQLite
        cursor.execute("""
        DELETE FROM journal_entries 
        WHERE source_document = ?
        """, (filename,))
        
        deleted_count = cursor.rowcount
        
        # Supprimer les tags devenus orphelins (associés uniquement aux entrées importées)
        for tag_id in tags_to_check:
            # Vérifier si ce tag est encore utilisé
            cursor.execute("""
            SELECT COUNT(*) FROM entry_tags WHERE tag_id = ?
            """, (tag_id,))
            
            tag_usage_count = cursor.fetchone()[0]
            
            if tag_usage_count == 0:
                # Récupérer le nom du tag pour le log
                cursor.execute("SELECT nom FROM tags WHERE id = ?", (tag_id,))
                tag_row = cursor.fetchone()
                tag_name = tag_row[0] if tag_row else f"ID {tag_id}"
                
                # Si le tag n'est plus utilisé, le supprimer
                cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
                print(f"Tag orphelin '{tag_name}' supprimé")
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success", 
            "message": f"{deleted_count} entrées issues de l'import '{filename}' supprimées",
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur lors du nettoyage de l'import '{filename}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Route pour nettoyer les tags orphelins
@app.delete("/admin/cleanup/orphan-tags")
async def cleanup_orphan_tags():
    """
    Nettoie tous les tags orphelins (non associés à des entrées) de la base de données
    et nettoie également les associations entry_tags pour des entrées qui n'existent plus
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. D'abord, supprimer les associations entry_tags qui pointent vers des entrées inexistantes
        cursor.execute("""
        DELETE FROM entry_tags 
        WHERE entry_id NOT IN (SELECT id FROM journal_entries)
        """)
        
        invalid_associations_count = cursor.rowcount
        print(f"Suppression de {invalid_associations_count} associations entry_tags invalides")
        
        # 2. Maintenant identifier les tags orphelins (qui ne sont associés à aucune entrée)
        cursor.execute("""
        SELECT t.id, t.nom
        FROM tags t
        LEFT JOIN entry_tags et ON t.id = et.tag_id
        WHERE et.entry_id IS NULL
        """)
        
        orphan_tags = [{"id": row[0], "nom": row[1]} for row in cursor.fetchall()]
        
        deleted_count = 0
        tag_names = []
        
        if orphan_tags:
            # Supprimer tous les tags orphelins
            orphan_ids = [tag["id"] for tag in orphan_tags]
            tag_names = [tag["nom"] for tag in orphan_tags]
            
            placeholders = ','.join(['?' for _ in orphan_ids])
            cursor.execute(f"DELETE FROM tags WHERE id IN ({placeholders})", orphan_ids)
            
            deleted_count = cursor.rowcount
            print(f"Suppression de {deleted_count} tags orphelins: {', '.join(tag_names)}")
        
        # 3. Vérifier s'il y a encore des associations et tags incohérents
        cursor.execute("SELECT COUNT(*) FROM entry_tags")
        et_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tags")
        tags_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM journal_entries")
        entries_count = cursor.fetchone()[0]
        
        print(f"État après nettoyage: {entries_count} entrées, {tags_count} tags, {et_count} associations")
        
        conn.commit()
        conn.close()
        
        # Retourner des informations détaillées
        return {
            "status": "success",
            "message": f"{deleted_count} tags orphelins supprimés, {invalid_associations_count} associations invalides nettoyées",
            "cleaned_tags_count": deleted_count,
            "cleaned_associations_count": invalid_associations_count,
            "removed_tags": tag_names,
            "remaining": {
                "entries": entries_count,
                "tags": tags_count,
                "associations": et_count
            }
        }
        
    except Exception as e:
        print(f"Erreur lors du nettoyage des tags orphelins: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Route pour nettoyer les tags spécifiques à l'importation
@app.delete("/admin/cleanup/import-tags")
async def cleanup_import_tags():
    """
    Nettoie les tags liés à l'importation comme 'import', 'erreur', etc.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Liste des tags à supprimer
        import_related_tags = ['import', 'erreur', 'importerreur', 'error', 'date_from_filename']
        
        # Supprimer les associations entre ces tags et les entrées
        for tag_name in import_related_tags:
            cursor.execute("""
            DELETE FROM entry_tags 
            WHERE tag_id IN (SELECT id FROM tags WHERE nom = ?)
            """, (tag_name,))
        
        # Supprimer les tags eux-mêmes
        placeholders = ','.join(['?' for _ in import_related_tags])
        cursor.execute(f"""
        DELETE FROM tags 
        WHERE nom IN ({placeholders})
        """, import_related_tags)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "message": f"{deleted_count} tags liés à l'importation supprimés",
            "cleaned_tags": import_related_tags
        }
        
    except Exception as e:
        print(f"Erreur lors du nettoyage des tags d'importation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Route pour nettoyer TOUS les tags liés aux entrées importées
@app.delete("/admin/cleanup/all-import-related-tags")
async def cleanup_all_import_related_tags():
    """
    Nettoie TOUS les tags liés à des entrées importées, même ceux comme 'microsoft' ou 'notre'.
    Cette fonction supprime tous les tags associés aux entrées de journal importées.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Identifie les IDs des entrées importées
        cursor.execute("""
        SELECT id FROM journal_entries 
        WHERE source_document IS NOT NULL AND source_document != ''
        """)
        
        import_entry_ids = [row[0] for row in cursor.fetchall()]
        
        if not import_entry_ids:
            conn.close()
            return {"status": "success", "message": "Aucune entrée importée trouvée", "cleaned_count": 0}
        
        # 2. Identifie tous les tags associés à ces entrées
        if import_entry_ids:
            placeholders = ','.join(['?' for _ in import_entry_ids])
            cursor.execute(f"""
            SELECT DISTINCT t.id, t.nom 
            FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            WHERE et.entry_id IN ({placeholders})
            """, import_entry_ids)
            
            import_tags = [{"id": row[0], "nom": row[1]} for row in cursor.fetchall()]
        else:
            import_tags = []
        
        if not import_tags:
            conn.close()
            return {"status": "success", "message": "Aucun tag associé aux imports trouvé", "cleaned_count": 0}
        
        # 3. Supprime les associations de ces tags avec TOUTES les entrées (pas seulement les imports)
        import_tag_ids = [tag["id"] for tag in import_tags]
        tag_placeholders = ','.join(['?' for _ in import_tag_ids])
        
        cursor.execute(f"""
        DELETE FROM entry_tags
        WHERE tag_id IN ({tag_placeholders})
        """, import_tag_ids)
        
        association_count = cursor.rowcount
        
        # 4. Supprime les tags eux-mêmes
        cursor.execute(f"""
        DELETE FROM tags
        WHERE id IN ({tag_placeholders})
        """, import_tag_ids)
        
        tag_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success", 
            "message": f"{tag_count} tags liés aux imports supprimés (et {association_count} associations)",
            "cleaned_count": tag_count,
            "removed_tags": [tag["nom"] for tag in import_tags]
        }
        
    except Exception as e:
        print(f"Erreur lors du nettoyage de tous les tags liés aux imports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Point d'entrée pour exécuter l'application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)