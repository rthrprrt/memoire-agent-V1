import os
import json
import httpx
import random
import logging
import hashlib
from typing import List, Optional, Dict, Any, AsyncGenerator

# Configuration du logger
logger = logging.getLogger(__name__)

class DeepseekConnectionError(Exception):
    """Erreur de connexion à l'API Deepseek"""
    pass

class DeepseekTimeoutError(Exception):
    """Délai d'attente dépassé pour Deepseek"""
    pass

class DeepseekResponseError(Exception):
    """Réponse invalide ou inattendue de Deepseek"""
    pass

class DeepseekManager:
    """
    Gestionnaire pour les interactions avec l'API Deepseek.
    """
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.chat_url = f"{base_url}/v1/chat/completions"
        self.embedding_url = f"{base_url}/v1/embeddings"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Génère du texte avec l'API Deepseek"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
            
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.chat_url, 
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                
                # Vérifier la structure de la réponse
                response_json = response.json()
                if "choices" not in response_json or not response_json["choices"]:
                    raise DeepseekResponseError("Format de réponse invalide: données 'choices' manquantes")
                    
                choice = response_json["choices"][0]
                if "message" not in choice or "content" not in choice["message"]:
                    raise DeepseekResponseError("Format de réponse invalide: message ou contenu manquant")
                
                return choice["message"]["content"]
                
        except httpx.TimeoutException as e:
            logger.error(f"Délai d'attente dépassé: {str(e)}")
            raise DeepseekTimeoutError(f"Le modèle {self.model} a mis trop de temps à répondre")
            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"Erreur HTTP {status_code} depuis Deepseek: {e.response.text}")
            
            if status_code == 401:
                raise DeepseekConnectionError("Clé API invalide ou absente")
            elif status_code == 404:
                raise DeepseekConnectionError(f"Modèle {self.model} non trouvé")
            elif status_code >= 500:
                raise DeepseekConnectionError(f"Erreur serveur Deepseek: {status_code}")
            else:
                raise DeepseekConnectionError(f"Erreur HTTP: {status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Erreur de connexion: {str(e)}")
            raise DeepseekConnectionError(f"Impossible de se connecter à Deepseek: {str(e)}")
            
        except KeyError as e:
            logger.error(f"Clé manquante dans la réponse: {str(e)}")
            raise DeepseekResponseError(f"Format de réponse inattendu: {str(e)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Impossible de décoder la réponse JSON: {str(e)}")
            raise DeepseekResponseError("Réponse non-JSON reçue")
            
        except Exception as e:
            logger.critical(f"Erreur inattendue: {str(e)}", exc_info=True)
            raise
    
    async def generate_text_streaming(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Génère du texte avec l'API Deepseek en mode streaming"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True  # Activer le streaming
        }
        
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream('POST', self.chat_url, json=payload, headers=self.headers) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = line[6:]  # Supprimer le préfixe "data: "
                                if data.strip() == "[DONE]":
                                    break
                                
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                            except json.JSONDecodeError:
                                logger.warning(f"Impossible de décoder le chunk JSON: {line}")
                                continue
                            except Exception as e:
                                logger.error(f"Erreur lors du traitement du chunk: {str(e)}")
                                continue
        except httpx.HTTPStatusError as e:
            logger.error(f"Erreur HTTP lors du streaming: {e.response.status_code}")
            yield f"Erreur de communication avec Deepseek: {e.response.status_code}"
        except httpx.RequestError as e:
            logger.error(f"Erreur de requête lors du streaming: {str(e)}")
            yield "Erreur de connexion à Deepseek"
        except Exception as e:
            logger.error(f"Erreur inattendue lors du streaming: {str(e)}")
            yield "Une erreur est survenue pendant la génération"
    
    async def get_embeddings(self, text: str) -> List[float]:
        """Obtient les embeddings d'un texte avec l'API Deepseek"""
        payload = {
            "model": "deepseek-embedding", # Modèle d'embedding de Deepseek
            "input": text
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.embedding_url, 
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                
                response_json = response.json()
                if "data" not in response_json or not response_json["data"]:
                    raise DeepseekResponseError("Format de réponse d'embedding invalide: données manquantes")
                
                # Récupérer le vecteur d'embedding
                embedding = response_json["data"][0]["embedding"]
                return embedding
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des embeddings: {str(e)}")
            # Fallback sur un vecteur par défaut
            return [0.0] * 1536  # Taille des embeddings Deepseek

class DeepseekOrchestrator:
    """
    Orchestrateur qui gère les modèles Deepseek et détermine
    lequel utiliser selon le type de tâche.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        # Initialiser les modèles avec leur configuration
        self.api_key = api_key
        self.base_url = base_url
        self.models = {
            "orchestrator": {
                "name": "deepseek-chat", # Modèle principal de Deepseek
                "description": "Modèle principal pour l'orchestration et la génération de contenu",
                "manager": None
            },
            "creator": {
                "name": "deepseek-chat", # Même modèle que l'orchestrateur
                "description": "Modèle pour la génération de contenu original",
                "manager": None
            },
            "improver": {
                "name": "deepseek-chat", # Même modèle que l'orchestrateur
                "description": "Modèle pour l'amélioration et la correction de texte",
                "manager": None
            },
            "reasoner": {
                "name": "deepseek-reasoner", # Modèle de raisonnement de Deepseek
                "description": "Modèle spécialisé pour le raisonnement et l'analyse complexe",
                "manager": None
            },
            "embedder": {
                "name": "deepseek-embedding", # Modèle d'embedding de Deepseek
                "description": "Modèle optimisé pour la génération d'embeddings",
                "manager": None
            }
        }
        
        # Initialiser les gestionnaires de modèles
        self._initialize_managers()
        
        # Cache pour les décisions de routage
        self.routing_cache = {}
        
    def _initialize_managers(self):
        """Initialise les gestionnaires DeepseekManager pour chaque modèle"""
        for model_key, model_info in self.models.items():
            model_info["manager"] = DeepseekManager(
                api_key=self.api_key,
                base_url=self.base_url,
                model=model_info["name"]
            )
            logger.info(f"Gestionnaire initialisé pour {model_key}: {model_info['name']}")
    
    async def route_task(self, task_type: str, query: str) -> str:
        """
        Détermine quel modèle utiliser en fonction du type de tâche.
        """
        # Routage explicite basé sur le type de tâche
        if task_type == "generate" or task_type == "plan":
            return "creator"
        elif task_type in ["improve", "grammar", "style"]:
            return "improver"
        elif task_type == "reasoning" or task_type == "analyze":
            return "reasoner"
        elif task_type == "embed":
            return "embedder"
        else:
            return "orchestrator"
    
    async def execute_task(self, task_type: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Exécute une tâche en la routant vers le modèle approprié
        et en récupérant la réponse.
        """
        try:
            # Déterminer le modèle à utiliser
            model_key = await self.route_task(task_type, prompt)
            logger.info(f"Tâche '{task_type}' routée vers modèle: {model_key}")
            
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
    
    async def generate_text_streaming(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        Génère du texte en streaming en utilisant le modèle principal.
        """
        try:
            # Utiliser l'orchestrateur par défaut pour le streaming
            model_manager = self.models["orchestrator"]["manager"]
            
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
            # Fallback sur un vecteur aléatoire
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
                # Génération d'un vecteur aléatoire comme dernier recours
                return [random.uniform(-0.1, 0.1) for _ in range(1536)]
        except Exception as e:
            logger.error(f"Échec du fallback local pour embeddings: {str(e)}")
            # Génération d'un vecteur aléatoire comme dernier recours
            return [random.uniform(-0.1, 0.1) for _ in range(1536)]