import os
import json
import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import chromadb
from chromadb.utils import embedding_functions
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
import logging

# Configuration de la journalisation
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Modèles de données
class JournalEntry(BaseModel):
    date: datetime
    content: str
    tags: List[str] = []
    
class MemoireSection(BaseModel):
    id: str
    title: str
    content: str
    parent_id: Optional[str] = None
    order: int
    last_modified: datetime
    version: int = 1

class VersionHistory(BaseModel):
    section_id: str
    version: int
    content: str
    timestamp: datetime
    comment: str = ""

class GenerateRequest(BaseModel):
    section_id: str
    prompt: Optional[str] = None

class ImproveRequest(BaseModel):
    section_id: str
    improvement_type: str = "style"  # style, grammar, depth, structure, concision

class ChatMessage(BaseModel):
    content: str
    relevant_journal: bool = True
    relevant_sections: bool = True

class Config:
    OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b")
    DB_PATH = os.getenv("DB_PATH", "./data")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vectordb")
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/memoire.db")
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50
    
# Initialisation de l'application
app = FastAPI(title="Memoire Assistant API")
config = Config()

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Création des dossiers nécessaires
os.makedirs(config.DB_PATH, exist_ok=True)
os.makedirs(config.VECTOR_DB_PATH, exist_ok=True)

# Initialisation de la base de données SQLite
def init_sqlite_db():
    conn = sqlite3.connect(config.SQLITE_DB_PATH)
    cursor = conn.cursor()
    
    # Table des sections du mémoire
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sections (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        parent_id TEXT,
        order_num INTEGER NOT NULL,
        last_modified TEXT NOT NULL,
        version INTEGER NOT NULL
    )
    ''')
    
    # Table de l'historique des versions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS version_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id TEXT NOT NULL,
        version INTEGER NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        comment TEXT,
        FOREIGN KEY (section_id) REFERENCES sections(id)
    )
    ''')
    
    # Table du journal de bord
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS journal_entries (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        content TEXT NOT NULL,
        tags TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Base de données SQLite initialisée")

# Initialisation de ChromaDB pour les embeddings
def init_chroma_db():
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    client = chromadb.PersistentClient(path=config.VECTOR_DB_PATH)
    
    # Collection pour les sections du mémoire
    try:
        sections_collection = client.get_collection("sections")
        logger.info("Collection 'sections' récupérée")
    except ValueError:
        sections_collection = client.create_collection(
            name="sections",
            embedding_function=sentence_transformer_ef
        )
        logger.info("Collection 'sections' créée")
    
    # Collection pour le journal de bord
    try:
        journal_collection = client.get_collection("journal")
        logger.info("Collection 'journal' récupérée")
    except ValueError:
        journal_collection = client.create_collection(
            name="journal",
            embedding_function=sentence_transformer_ef
        )
        logger.info("Collection 'journal' créée")
    
    return client

# Initialisation des bases de données
init_sqlite_db()
chroma_client = init_chroma_db()

# Client HTTP pour communiquer avec Ollama
http_client = httpx.AsyncClient(timeout=60.0)

# Classe pour gérer les interactions avec Ollama
class OllamaManager:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model
        self.generate_url = f"{base_url}/api/generate"
        self.embedding_url = f"{base_url}/api/embeddings"
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Génère du texte avec Ollama"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = await http_client.post(self.generate_url, json=payload)
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            logger.error(f"Erreur lors de la génération de texte avec Ollama: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Erreur Ollama: {str(e)}")
    
    async def get_embeddings(self, text: str) -> List[float]:
        """Obtient les embeddings d'un texte avec Ollama"""
        payload = {
            "model": self.model,
            "prompt": text
        }
        
        try:
            response = await http_client.post(self.embedding_url, json=payload)
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des embeddings: {str(e)}")
            # Utiliser une fonction de repli local si Ollama échoue
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """Fonction de repli si Ollama échoue pour les embeddings"""
        # Cette fonction pourrait utiliser une bibliothèque locale comme sentence-transformers
        # Pour l'instant, nous retournons un vecteur aléatoire (pour la démo uniquement)
        return [0] * 768  # Taille typique d'embedding

ollama_manager = OllamaManager(config.OLLAMA_BASE_URL, config.OLLAMA_MODEL)

# TextSplitter pour le chunking des documents
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    length_function=len
)

# Classe pour gérer la mémoire et la persistance
class MemoryManager:
    def __init__(self, sqlite_path: str, chroma_client):
        self.sqlite_path = sqlite_path
        self.chroma_client = chroma_client
        self.sections_collection = chroma_client.get_collection("sections")
        self.journal_collection = chroma_client.get_collection("journal")
    
    def _get_sqlite_connection(self):
        """Obtient une connexion à la base de données SQLite"""
        return sqlite3.connect(self.sqlite_path)
    
    async def save_section(self, section: MemoireSection) -> MemoireSection:
        """Sauvegarde une section du mémoire"""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        # Vérifier si la section existe déjà
        cursor.execute("SELECT * FROM sections WHERE id = ?", (section.id,))
        existing = cursor.fetchone()
        
        if existing:
            # Créer une entrée d'historique
            version = existing[6]  # version dans la DB
            cursor.execute(
                "INSERT INTO version_history (section_id, version, content, timestamp, comment) VALUES (?, ?, ?, ?, ?)",
                (section.id, version, existing[2], existing[5], "Version automatique")
            )
            
            # Mettre à jour la section
            section.version = version + 1
            cursor.execute(
                "UPDATE sections SET title = ?, content = ?, parent_id = ?, order_num = ?, last_modified = ?, version = ? WHERE id = ?",
                (section.title, section.content, section.parent_id, section.order, section.last_modified.isoformat(), section.version, section.id)
            )
        else:
            # Insérer une nouvelle section
            cursor.execute(
                "INSERT INTO sections (id, title, content, parent_id, order_num, last_modified, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (section.id, section.title, section.content, section.parent_id, section.order, section.last_modified.isoformat(), section.version)
            )
        
        conn.commit()
        conn.close()
        
        # Indexer le contenu pour la recherche vectorielle
        await self._index_section_content(section)
        
        return section
    
    async def _index_section_content(self, section: MemoireSection):
        """Indexe le contenu d'une section dans ChromaDB"""
        # Diviser le contenu en chunks
        chunks = text_splitter.split_text(section.content)
        
        # Supprimer les chunks existants pour cette section
        try:
            existing_ids = [f"{section.id}_{i}" for i in range(100)]  # Hypothèse max 100 chunks
            self.sections_collection.delete(ids=existing_ids, where={"section_id": section.id})
        except Exception as e:
            logger.warning(f"Erreur lors de la suppression des chunks existants: {str(e)}")
        
        # Ajouter les nouveaux chunks
        if chunks:
            ids = [f"{section.id}_{i}" for i in range(len(chunks))]
            metadata = [{"section_id": section.id, "title": section.title, "chunk_index": i} for i in range(len(chunks))]
            
            self.sections_collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadata
            )
            logger.info(f"Indexé {len(chunks)} chunks pour la section {section.id}")
    
    async def get_section(self, section_id: str) -> MemoireSection:
        """Récupère une section par son ID"""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM sections WHERE id = ?", (section_id,))
        result = cursor.fetchone()
        
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Section not found")
        
        return MemoireSection(
            id=result[0],
            title=result[1],
            content=result[2],
            parent_id=result[3],
            order=result[4],
            last_modified=datetime.fromisoformat(result[5]),
            version=result[6]
        )
    
    async def get_outline(self) -> List[Dict[str, Any]]:
        """Récupère la structure du plan du mémoire"""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, title, parent_id, order_num FROM sections ORDER BY order_num")
        results = cursor.fetchall()
        
        conn.close()
        
        sections = []
        for result in results:
            sections.append({
                "id": result[0],
                "title": result[1],
                "parent_id": result[2],
                "order": result[3]
            })
        
        # Organiser en structure hiérarchique
        root_sections = [s for s in sections if not s["parent_id"]]
        for root in root_sections:
            root["children"] = self._get_children(root["id"], sections)
        
        return sorted(root_sections, key=lambda x: x["order"])
    
    def _get_children(self, parent_id: str, all_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fonction récursive pour construire l'arborescence"""
        children = [s for s in all_sections if s.get("parent_id") == parent_id]
        for child in children:
            child["children"] = self._get_children(child["id"], all_sections)
        return sorted(children, key=lambda x: x["order"])
    
    async def search_relevant_journal(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recherche les entrées de journal pertinentes pour une requête"""
        try:
            results = self.journal_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            if not results["ids"][0]:
                return []
            
            entries = []
            for i, doc_id in enumerate(results["ids"][0]):
                # Extraire l'ID réel de l'entrée (sans le _chunk_index)
                entry_id = doc_id.split("_")[0]
                
                # Récupérer l'entrée complète
                conn = self._get_sqlite_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,))
                entry = cursor.fetchone()
                conn.close()
                
                if entry:
                    entries.append({
                        "id": entry[0],
                        "date": entry[1],
                        "content": entry[2],
                        "tags": json.loads(entry[3]) if entry[3] else [],
                        "relevance_score": results["distances"][0][i] if "distances" in results else 1.0
                    })
            
            # Éliminer les doublons (par id)
            unique_entries = []
            seen_ids = set()
            for entry in entries:
                if entry["id"] not in seen_ids:
                    unique_entries.append(entry)
                    seen_ids.add(entry["id"])
            
            return unique_entries
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans le journal: {str(e)}")
            return []
    
    async def search_relevant_sections(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recherche les sections pertinentes pour une requête"""
        try:
            results = self.sections_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            if not results["ids"][0]:
                return []
            
            sections = []
            for i, doc_id in enumerate(results["ids"][0]):
                # Extraire l'ID de la section
                section_id = results["metadatas"][0][i]["section_id"]
                
                # Éviter les doublons
                if not any(s["id"] == section_id for s in sections):
                    # Récupérer la section complète
                    try:
                        section = await self.get_section(section_id)
                        sections.append({
                            "id": section.id,
                            "title": section.title,
                            "content_preview": section.content[:200] + "..." if len(section.content) > 200 else section.content,
                            "relevance_score": results["distances"][0][i] if "distances" in results else 1.0
                        })
                    except HTTPException:
                        pass  # Ignorer si la section n'est pas trouvée
            
            return sections
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de sections: {str(e)}")
            return []
    
    async def add_journal_entry(self, entry: JournalEntry) -> Dict[str, Any]:
        """Ajoute une entrée au journal de bord"""
        # Créer un ID
        entry_id = str(uuid.uuid4())
        
        # Sauvegarder l'entrée
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO journal_entries (id, date, content, tags) VALUES (?, ?, ?, ?)",
            (entry_id, entry.date.isoformat(), entry.content, json.dumps(entry.tags))
        )
        
        conn.commit()
        conn.close()
        
        # Indexer pour la recherche vectorielle
        chunks = text_splitter.split_text(entry.content)
        
        if chunks:
            ids = [f"{entry_id}_{i}" for i in range(len(chunks))]
            metadata = [{
                "entry_id": entry_id,
                "date": entry.date.isoformat(),
                "tags": json.dumps(entry.tags),
                "chunk_index": i
            } for i in range(len(chunks))]
            
            self.journal_collection.add(
                ids=ids,
                documents=chunks,
                metadatas=metadata
            )
        
        return {
            "id": entry_id,
            "date": entry.date,
            "content": entry.content,
            "tags": entry.tags
        }
    
    async def get_journal_entries(self, limit: int = 50, skip: int = 0) -> List[Dict[str, Any]]:
        """Récupère les entrées du journal de bord"""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM journal_entries ORDER BY date DESC LIMIT ? OFFSET ?", (limit, skip))
        results = cursor.fetchall()
        
        conn.close()
        
        entries = []
        for result in results:
            entries.append({
                "id": result[0],
                "date": result[1],
                "content": result[2],
                "tags": json.loads(result[3]) if result[3] else []
            })
        
        return entries

memory_manager = MemoryManager(config.SQLITE_DB_PATH, chroma_client)

# Gestionnaire LLM pour la génération de contenu
class LLMManager:
    def __init__(self, ollama_manager: OllamaManager):
        self.ollama = ollama_manager
    
    async def generate_section_content(
        self,
        section_title: str,
        section_description: str,
        journal_entries: List[Dict[str, Any]],
        current_outline: List[Dict[str, Any]]
    ) -> str:
        """Génère du contenu pour une section basé sur le journal et le plan"""
        
        # Limiter la longueur pour respecter les limites du modèle
        journal_content = ""
        for entry in journal_entries[:5]:  # Limiter à 5 entrées pour éviter de dépasser le contexte
            content_preview = entry["content"][:500] + "..." if len(entry["content"]) > 500 else entry["content"]
            journal_content += f"\n## Date: {entry['date']}\n{content_preview}\n"
        
        # Simplifier l'outline pour le prompt
        simplified_outline = json.dumps([{
            "title": section.get("title", ""),
            "id": section.get("id", "")
        } for section in current_outline], indent=2)
        
        system_prompt = """
        Vous êtes un assistant d'écriture de mémoire professionnel. Vous devez générer du contenu pour 
        une section d'un mémoire d'alternance pour le titre RNCP 35284 Expert en management des 
        systèmes d'information. Appuyez-vous sur les entrées du journal fournies et respectez la 
        structure du mémoire. Votre réponse doit être analytique, réflexive et bien structurée.
        """
        
        user_prompt = f"""
        # Section à rédiger
        Titre: {section_title}
        Description: {section_description}
        
        # Structure du mémoire
        {simplified_outline}
        
        # Entrées pertinentes du journal de bord
        {journal_content}
        
        Rédigez un contenu détaillé, analytique et réflexif pour cette section. 
        Utilisez les entrées du journal comme source d'exemples et d'illustrations.
        Assurez-vous que le contenu est bien structuré, avec une introduction, un développement
        et une conclusion si nécessaire. Ne mentionnez pas explicitement que vous utilisez le journal,
        intégrez naturellement ces informations dans le texte.
        """
        
        return await self.ollama.generate_text(user_prompt, system_prompt)
    
    async def generate_initial_outline(self, journal_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Génère un plan initial basé sur le journal de bord"""
        # Agréger les entrées du journal
        journal_content = ""
        for entry in journal_entries[:10]:  # Limiter pour éviter de dépasser le contexte
            content_preview = entry["content"][:300] + "..." if len(entry["content"]) > 300 else entry["content"]
            journal_content += f"\n## Date: {entry['date']}\n{content_preview}\n"
        
        system_prompt = """
        Vous êtes un expert en rédaction de mémoires professionnels. Vous devez générer un plan 
        structuré pour un mémoire d'alternance pour le titre RNCP 35284 Expert en management des 
        systèmes d'information. Respectez la structure demandée et basez-vous sur les entrées du journal
        pour personnaliser le contenu.
        """
        
        user_prompt = f"""
        Le mémoire doit suivre la structure générale suivante:
        1. Introduction (entreprise, contexte, objectifs)
        2. Description de la mission
        3. Analyse des compétences
        4. Évaluation de la performance
        5. Réflexion personnelle et professionnelle
        6. Conclusion
        7. Annexes
        
        Voici un extrait du journal de bord de l'alternance:
        
        {journal_content}
        
        Générez un plan détaillé avec:
        - Les chapitres principaux (niveaux 1)
        - Les sous-sections (niveaux 2)
        - Une brève description de chaque section
        
        Répondez au format JSON avec la structure suivante:
        [
          {{
            "id": "chapitre-1",
            "title": "Titre du chapitre",
            "description": "Description du chapitre",
            "order": 1,
            "children": [
              {{
                "id": "section-1-1",
                "title": "Titre de la section",
                "description": "Description de la section",
                "parent_id": "chapitre-1",
                "order": 1,
                "children": []
              }}
            ]
          }}
        ]
        
        Assurez-vous que le JSON est valide et bien formaté.
        """
        
        response = await self.ollama.generate_text(user_prompt, system_prompt)
        
        # Extraire le JSON de la réponse
        try:
            # Trouver les délimiteurs du JSON
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("Délimiteurs JSON non trouvés")
            
            json_str = response[json_start:json_end]
            outline = json.loads(json_str)
            return outline
        except Exception as e:
            logger.error(f"Erreur lors du parsing de la réponse LLM: {str(e)}")
            logger.debug(f"Réponse reçue: {response}")
            
            # Plan par défaut en cas d'échec
            return [
                {
                    "id": "intro",
                    "title": "1. Introduction",
                    "description": "Présentation de l'entreprise et contexte de la mission",
                    "order": 1,
                    "children": [
                        {
                            "id": "intro-entreprise",
                            "title": "1.1 Présentation de l'entreprise",
                            "description": "Description de l'entreprise, son activité et son marché",
                            "parent_id": "intro",
                            "order": 1,
                            "children": []
                        },
                        {
                            "id": "intro-contexte",
                            "title": "1.2 Contexte de la mission",
                            "description": "Contexte et objectifs de la mission d'alternance",
                            "parent_id": "intro",
                            "order": 2,
                            "children": []
                        }
                    ]
                },
                {
                    "id": "mission",
                    "title": "2. Description de la mission",
                    "description": "Détail des tâches et responsabilités",
                    "order": 2,
                    "children": []
                },
                {
                    "id": "competences",
                    "title": "3. Analyse des compétences",
                    "description": "Analyse des compétences développées",
                    "order": 3,
                    "children": []
                },
                {
                    "id": "evaluation",
                    "title": "4. Évaluation de la performance",
                    "description": "Auto-évaluation et feedback reçus",
                    "order": 4,
                    "children": []
                },
                {
                    "id": "reflexion",
                    "title": "5. Réflexion personnelle et professionnelle",
                    "description": "Réflexion sur l'expérience et l'évolution personnelle",
                    "order": 5,
                    "children": []
                },
                {
                    "id": "conclusion",
                    "title": "6. Conclusion",
                    "description": "Synthèse et perspectives",
                    "order": 6,
                    "children": []
                }
            ]
    
    async def improve_text(self, text: str, improvement_type: str) -> str:
        """Améliore un texte selon le type d'amélioration demandé"""
        prompt_map = {
            "style": "Améliorez le style d'écriture du texte suivant pour le rendre plus professionnel et fluide.",
            "grammar": "Corrigez la grammaire et l'orthographe du texte suivant.",
            "structure": "Améliorez la structure du texte suivant en ajoutant des paragraphes, des transitions et des sous-titres si nécessaire.",
            "depth": "Approfondissez l'analyse dans le texte suivant en ajoutant plus de réflexion critique.",
            "concision": "Rendez le texte suivant plus concis sans perdre d'information importante."
        }
        
        system_prompt = "Vous êtes un assistant d'écriture professionnel qui aide à améliorer des textes académiques."
        
        user_prompt = f"""
        {prompt_map.get(improvement_type, "Améliorez le texte suivant.")}
        
        Texte original:
        {text}
        
        Texte amélioré:
        """
        
        return await self.ollama.generate_text(user_prompt, system_prompt)

llm_manager = LLMManager(ollama_manager)

# Routes API
@app.get("/")
async def root():
    return {"message": "Memoire Assistant API", "status": "running"}

# Routes pour le plan
@app.get("/api/outline")
async def get_outline():
    """Récupère la structure du plan du mémoire"""
    return await memory_manager.get_outline()

@app.post("/api/outline")
async def create_initial_outline():
    """Crée un plan initial basé sur le journal de bord"""
    # Récupérer les entrées du journal
    journal_entries = await memory_manager.get_journal_entries(limit=20)
    
    # Générer le plan initial
    outline = await llm_manager.generate_initial_outline(journal_entries)
    
    # Sauvegarder le plan
    for section in outline:
        await save_section_recursive(section, memory_manager)
    
    return outline

async def save_section_recursive(section, memory_manager):
    """Sauvegarde récursivement une section et ses enfants"""
    children = section.pop("children", [])
    
    # Créer et sauvegarder la section
    section_model = MemoireSection(
        id=section["id"],
        title=section["title"],
        content=section.get("description", ""),
        parent_id=section.get("parent_id"),
        order=section["order"],
        last_modified=datetime.now()
    )
    await memory_manager.save_section(section_model)
    
    # Sauvegarder les enfants
    for child in children:
        child["parent_id"] = section["id"]
        await save_section_recursive(child, memory_manager)

# Routes pour les sections
@app.get("/api/section/{section_id}")
async def get_section(section_id: str):
    """Récupère une section par son ID"""
    return await memory_manager.get_section(section_id)

@app.post("/api/section/{section_id}/generate")
async def generate_section_content(section_id: str, request: GenerateRequest):
    """Génère du contenu pour une section"""
    # Récupérer la section
    section = await memory_manager.get_section(section_id)
    
    # Récupérer le plan actuel
    outline = await memory_manager.get_outline()
    
    # Trouver des entrées de journal pertinentes
    query = request.prompt if request.prompt else section.title + " " + section.content
    relevant_entries = await memory_manager.search_relevant_journal(query)
    
    # Générer le contenu
    content = await llm_manager.generate_section_content(
        section.title,
        section.content,  # La description est stockée dans le contenu initialement
        relevant_entries,
        outline
    )
    
    # Mettre à jour la section
    section.content = content
    section.last_modified = datetime.now()
    await memory_manager.save_section(section)
    
    return section

@app.post("/api/section/{section_id}/improve")
async def improve_section(section_id: str, request: ImproveRequest):
    """Améliore le contenu d'une section"""
    # Récupérer la section
    section = await memory_manager.get_section(section_id)
    
    # Améliorer le contenu
    improved_content = await llm_manager.improve_text(section.content, request.improvement_type)
    
    # Mettre à jour la section
    section.content = improved_content
    section.last_modified = datetime.now()
    await memory_manager.save_section(section)
    
    return section

@app.put("/api/section/{section_id}")
async def update_section(section_id: str, section: MemoireSection):
    """Met à jour une section existante"""
    if section_id != section.id:
        raise HTTPException(status_code=400, detail="Section ID mismatch")
    
    section.last_modified = datetime.now()
    return await memory_manager.save_section(section)

# Routes pour le journal de bord
@app.post("/api/journal")
async def add_journal_entry(entry: JournalEntry):
    """Ajoute une entrée au journal de bord"""
    return await memory_manager.add_journal_entry(entry)

@app.get("/api/journal")
async def get_journal_entries(limit: int = 50, skip: int = 0):
    """Récupère les entrées du journal de bord"""
    return await memory_manager.get_journal_entries(limit, skip)

@app.post("/api/chat")
async def chat(message: ChatMessage):
    """Point d'API pour le chat"""
    # Récupérer du contenu pertinent si demandé
    relevant_journal = []
    relevant_sections = []
    
    if message.relevant_journal:
        relevant_journal = await memory_manager.search_relevant_journal(message.content)
    
    if message.relevant_sections:
        relevant_sections = await memory_manager.search_relevant_sections(message.content)
    
    # Construire le contexte pour le LLM
    journal_content = ""
    for entry in relevant_journal[:3]:
        journal_content += f"\n## Date: {entry['date']}\n{entry['content'][:300]}...\n"
    
    sections_content = ""
    for section in relevant_sections[:2]:
        sections_content += f"\n## {section['title']}\n{section['content_preview']}\n"
    
    system_prompt = """
    Vous êtes un assistant d'écriture de mémoire professionnel. Répondez aux questions de l'utilisateur
    en vous appuyant sur le contenu du journal de bord et des sections du mémoire si pertinent.
    Soyez concis, précis et utile.
    """
    
    user_prompt = f"""
    Question: {message.content}
    
    Informations pertinentes du journal de bord:
    {journal_content if journal_content else "Aucune entrée pertinente trouvée."}
    
    Sections pertinentes du mémoire:
    {sections_content if sections_content else "Aucune section pertinente trouvée."}
    
    Veuillez répondre à la question en vous basant sur ces informations si pertinent.
    """
    
    response = await ollama_manager.generate_text(user_prompt, system_prompt)
    
    return {
        "response": response,
        "context": {
            "journal_entries_used": len(relevant_journal),
            "sections_used": len(relevant_sections)
        }
    }

# WebSocket pour le chat interactif
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Traiter différents types de messages
            if message["type"] == "chat":
                # Récupérer du contenu pertinent
                query = message["content"]
                relevant_journal = await memory_manager.search_relevant_journal(query)
                relevant_sections = await memory_manager.search_relevant_sections(query)
                
                # Construire le contexte pour le LLM
                journal_content = ""
                for entry in relevant_journal[:3]:
                    journal_content += f"\n## Date: {entry['date']}\n{entry['content'][:300]}...\n"
                
                sections_content = ""
                for section in relevant_sections[:2]:
                    sections_content += f"\n## {section['title']}\n{section['content_preview']}\n"
                
                system_prompt = """
                Vous êtes un assistant d'écriture de mémoire professionnel. Répondez aux questions de l'utilisateur
                en vous appuyant sur le contenu du journal de bord et des sections du mémoire si pertinent.
                Soyez concis, précis et utile.
                """
                
                user_prompt = f"""
                Question: {query}
                
                Informations pertinentes du journal de bord:
                {journal_content if journal_content else "Aucune entrée pertinente trouvée."}
                
                Sections pertinentes du mémoire:
                {sections_content if sections_content else "Aucune section pertinente trouvée."}
                
                Veuillez répondre à la question en vous basant sur ces informations si pertinent.
                """
                
                response = await ollama_manager.generate_text(user_prompt, system_prompt)
                
                await websocket.send_text(json.dumps({
                    "type": "chat_response",
                    "content": response,
                    "context": {
                        "journal_entries_used": len(relevant_journal),
                        "sections_used": len(relevant_sections)
                    }
                }))
            
            elif message["type"] == "update_section":
                # Mettre à jour une section
                section_id = message["section_id"]
                content = message["content"]
                
                section = await memory_manager.get_section(section_id)
                section.content = content
                section.last_modified = datetime.now()
                await memory_manager.save_section(section)
                
                await websocket.send_text(json.dumps({
                    "type": "section_updated",
                    "section_id": section_id
                }))
            
            # Autres types de messages à implémenter...
                
    except WebSocketDisconnect:
        logger.info("WebSocket déconnecté")
    except Exception as e:
        logger.error(f"Erreur WebSocket: {str(e)}")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)