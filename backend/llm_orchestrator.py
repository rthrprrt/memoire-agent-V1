import os
import json
import httpx
import random
import hashlib
import logging
from typing import List, Optional, Dict, AsyncGenerator

# Configuration du logger
logger = logging.getLogger(__name__)

class OllamaConnectionError(Exception):
    """Erreur de connexion à Ollama"""
    pass

class OllamaTimeoutError(Exception):
    """Délai d'attente dépassé pour Ollama"""
    pass

class OllamaResponseError(Exception):
    """Réponse invalide ou inattendue d'Ollama"""
    pass

class OllamaManager:
    """
    Gestionnaire pour les interactions avec un modèle Ollama spécifique.
    """
    def __init__(self, base_url: str, model: str):
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
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.generate_url, json=payload)
                response.raise_for_status()
                
                # Vérifier la structure de la réponse
                if "response" not in response.json():
                    raise OllamaResponseError("Format de réponse invalide: clé 'response' manquante")
                    
                return response.json()["response"]
                
        except httpx.TimeoutException as e:
            logger.error(f"Délai d'attente dépassé: {str(e)}")
            raise OllamaTimeoutError(f"Le modèle {self.model} a mis trop de temps à répondre")
            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"Erreur HTTP {status_code} depuis Ollama: {e.response.text}")
            
            if status_code == 404:
                raise OllamaConnectionError(f"Modèle {self.model} non trouvé")
            elif status_code >= 500:
                raise OllamaConnectionError(f"Erreur serveur Ollama: {status_code}")
            else:
                raise OllamaConnectionError(f"Erreur HTTP: {status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Erreur de connexion: {str(e)}")
            raise OllamaConnectionError(f"Impossible de se connecter à Ollama: {str(e)}")
            
        except KeyError as e:
            logger.error(f"Clé manquante dans la réponse: {str(e)}")
            raise OllamaResponseError(f"Format de réponse inattendu: {str(e)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Impossible de décoder la réponse JSON: {str(e)}")
            raise OllamaResponseError("Réponse non-JSON reçue")
            
        except Exception as e:
            logger.critical(f"Erreur inattendue: {str(e)}", exc_info=True)
            raise
    
    async def generate_text_streaming(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Génère du texte avec Ollama en mode streaming"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True  # Activer le streaming
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream('POST', self.generate_url, json=payload) as response:
                    response.raise_for_status()
                    
                    buffer = ""
                    async for chunk in response.aiter_text():
                        try:
                            if chunk.strip():
                                data = json.loads(chunk)
                                if "response" in data:
                                    text_chunk = data["response"]
                                    buffer += text_chunk
                                    
                                    # Envoyer des segments de phrase complets
                                    if any(c in buffer for c in ['.', '!', '?', '\n']):
                                        yield buffer
                                        buffer = ""
                                        
                                if data.get("done", False) and buffer:
                                    # Envoyer le reste du buffer à la fin
                                    yield buffer
                        except json.JSONDecodeError:
                            logger.warning(f"Impossible de décoder le chunk JSON: {chunk}")
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP lors du streaming: {e.response.status_code}")
            yield f"Erreur de communication avec le LLM: {e.response.status_code}"
        except httpx.RequestError as e:
            logger.error(f"Erreur de requête lors du streaming: {str(e)}")
            yield "Erreur de connexion au LLM"
        except Exception as e:
            logger.error(f"Erreur inattendue lors du streaming: {str(e)}")
            yield "Une erreur est survenue pendant la génération"
    
    async def get_embeddings(self, text: str) -> List[float]:
        """Obtient les embeddings d'un texte avec Ollama"""
        payload = {
            "model": self.model,
            "prompt": text
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.embedding_url, json=payload)
                response.raise_for_status()
                return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des embeddings: {str(e)}")
            # Fallback sur un vecteur par défaut
            return [0.0] * 768  # Taille typique d'embedding

class LLMOrchestrator:
    """
    Orchestrateur qui gère plusieurs modèles LLM spécialisés et détermine
    lequel utiliser selon le type de tâche.
    """
    def __init__(self, base_url: str = "http://localhost:11434"):
        # Initialiser les modèles avec leur configuration
        self.base_url = base_url
        self.models = {
            "orchestrator": {
                "name": "llama3:8b-q4_0", # Modèle léger pour les décisions de routage
                "description": "Modèle léger pour l'orchestration et le routage des requêtes",
                "manager": None
            },
            "creator": {
                "name": "llama3:70b-q4_K_M", # Modèle plus puissant pour la génération créative
                "description": "Modèle puissant pour la génération de contenu original",
                "manager": None
            },
            "improver": {
                "name": "mistral:7b-instruct-v0.2-q4_K_M", # Bon pour les instructions précises
                "description": "Modèle spécialisé pour l'amélioration et la correction de texte",
                "manager": None
            },
            "embedder": {
                "name": "nomic-embed-text:latest", # Modèle d'embedding léger et efficace
                "description": "Modèle optimisé pour la génération d'embeddings",
                "manager": None
            }
        }
        
        # Initialiser les gestionnaires de modèles
        self._initialize_managers()
        
        # Cache pour les décisions de routage
        self.routing_cache = {}
        
    def _initialize_managers(self):
        """Initialise les gestionnaires OllamaManager pour chaque modèle"""
        for model_key, model_info in self.models.items():
            model_info["manager"] = OllamaManager(
                base_url=self.base_url,
                model=model_info["name"]
            )
            logger.info(f"Gestionnaire initialisé pour {model_key}: {model_info['name']}")
    
    async def route_task(self, task_type: str, query: str) -> str:
        """
        Détermine quel modèle utiliser en fonction du type de tâche.
        Si le type est 'auto', analyse la requête pour déterminer le modèle.
        """
        if task_type != "auto":
            # Routage explicite basé sur le type de tâche
            if task_type == "generate":
                return "creator"
            elif task_type in ["improve", "grammar", "style"]:
                return "improver"
            elif task_type == "embed":
                return "embedder"
            else:
                return "orchestrator"
        
        # Routage automatique basé sur l'analyse de la requête
        # Vérifier d'abord le cache pour éviter de reconsulter l'orchestrateur
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.routing_cache:
            return self.routing_cache[cache_key]
        
        # Demander à l'orchestrateur de déterminer le modèle approprié
        system_prompt = """
        Vous êtes un système d'orchestration de modèles LLM. Votre tâche est d'analyser 
        une requête et de déterminer quel modèle spécialisé doit la traiter.
        
        Les modèles disponibles sont:
        - creator: Pour la génération créative de contenu original (rédaction, plans, sections)
        - improver: Pour l'amélioration et la correction de texte existant
        - embedder: Pour les tâches de recherche sémantique
        - orchestrator: Pour les tâches générales de compréhension et d'analyse
        
        Répondez uniquement avec le nom du modèle à utiliser, sans autre texte.
        """
        
        user_prompt = f"""
        Analysez la requête suivante et déterminez quel modèle doit la traiter:
        
        {query}
        
        Répondez uniquement avec un de ces noms: creator, improver, embedder, orchestrator.
        """
        
        # Obtenir la décision de l'orchestrateur
        orchestrator = self.models["orchestrator"]["manager"]
        try:
            decision = await orchestrator.generate_text(user_prompt, system_prompt)
            # Nettoyer la réponse
            decision = decision.strip().lower()
            # Vérifier que la réponse est valide
            if decision not in ["creator", "improver", "embedder", "orchestrator"]:
                logger.warning(f"Décision de routage invalide: {decision}, fallback sur orchestrator")
                decision = "orchestrator"
            
            # Mettre en cache pour les futures requêtes similaires
            self.routing_cache[cache_key] = decision
            
            return decision
        except Exception as e:
            logger.error(f"Erreur lors du routage de la tâche: {str(e)}")
            return "orchestrator"  # Modèle par défaut en cas d'erreur
    
    async def execute_task(self, task: str, prompt: str, system_prompt: str = None) -> str:
        """
        Exécute une tâche en la routant vers le modèle approprié
        et en récupérant la réponse.
        """
        try:
            # Déterminer le modèle à utiliser
            model_key = await self.route_task(task, prompt)
            logger.info(f"Tâche '{task}' routée vers modèle: {model_key}")
            
            # Récupérer le gestionnaire du modèle
            model_manager = self.models[model_key]["manager"]
            
            # Exécuter la requête
            response = await model_manager.generate_text(prompt, system_prompt)
            return response
        
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche: {str(e)}")
            # En cas d'erreur, essayer avec le modèle orchestrateur
            try:
                return await self.models["orchestrator"]["manager"].generate_text(
                    prompt, 
                    system_prompt or "Vous êtes un assistant d'écriture académique utile et précis."
                )
            except:
                return "Désolé, je ne peux pas traiter cette demande pour le moment."
    
    async def generate_text_streaming(self, task: str, prompt: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """
        Génère du texte en streaming en utilisant le modèle approprié.
        """
        try:
            # Déterminer le modèle à utiliser
            model_key = await self.route_task(task, prompt)
            logger.info(f"Tâche de streaming '{task}' routée vers modèle: {model_key}")
            
            # Récupérer le gestionnaire du modèle
            model_manager = self.models[model_key]["manager"]
            
            # Exécuter la requête en streaming
            async for chunk in model_manager.generate_text_streaming(prompt, system_prompt):
                yield chunk
        
        except Exception as e:
            logger.error(f"Erreur lors du streaming: {str(e)}")
            yield f"Erreur: {str(e)}"
    
    async def get_embeddings(self, text: str) -> List[float]:
        """
        Génère des embeddings en utilisant le modèle optimisé pour cette tâche.
        """
        try:
            embedder = self.models["embedder"]["manager"]
            return await embedder.get_embeddings(text)
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings: {str(e)}")
            # Fallback sur un autre modèle si le modèle d'embedding échoue
            try:
                return await self.models["orchestrator"]["manager"].get_embeddings(text)
            except:
                # Dernier recours: embedding local via sentence-transformers
                return self._local_embedding_fallback(text)

def _local_embedding_fallback(self, text: str) -> List[float]:
    """
    Génère des embeddings localement si possible, sinon retourne un vecteur aléatoire.
    """
    try:
        try:
            from sentence_transformers import SentenceTransformer
            # On utilise un modèle léger qui devrait être rapide
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embedding = model.encode([text])[0].tolist()
            logger.info("Embeddings générés localement via sentence-transformers")
            return embedding
        except ImportError:
            logger.warning("sentence-transformers n'est pas installé. Utilisation d'un vecteur aléatoire.")
            # Génération d'un vecteur aléatoire de dimension 384 comme dernier recours
            return [random.uniform(-0.1, 0.1) for _ in range(384)]
    except Exception as e:
        logger.error(f"Échec du fallback local pour embeddings: {str(e)}")
        # Génération d'un vecteur aléatoire de dimension 384 comme dernier recours
        return [random.uniform(-0.1, 0.1) for _ in range(384)]