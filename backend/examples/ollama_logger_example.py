"""
Exemple d'intégration de logs pour les interactions avec Ollama
Ce module montre comment implémenter des logs détaillés pour les appels à l'API Ollama.
"""

import os
import time
import json
import httpx
from typing import Dict, Any, Optional, List, Tuple, Union

# S'assurer que le dossier examples existe
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)

# Importer le logger configuré
try:
    from core.logging_config import get_logger
    logger = get_logger("ollama_client")
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("ollama_client")

class OllamaClient:
    """
    Client pour l'API Ollama avec logging avancé
    """
    
    def __init__(self, base_url: str = None, default_model: str = None, timeout: int = 30):
        """
        Initialise le client Ollama
        
        Args:
            base_url: URL de base pour l'API Ollama, default http://localhost:11434
            default_model: Modèle par défaut à utiliser, default mistral:7b
            timeout: Timeout en secondes pour les requêtes, default 30
        """
        self.base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.default_model = default_model or os.environ.get("OLLAMA_MODEL", "mistral:7b")
        self.timeout = timeout
        self.client = httpx.Client(timeout=self.timeout)
        
        logger.info(f"OllamaClient initialisé avec base_url={self.base_url}, default_model={self.default_model}")
    
    def _log_request(self, endpoint: str, method: str, data: Dict[str, Any] = None) -> None:
        """Log les détails de la requête"""
        request_id = f"req_{int(time.time() * 1000)}"
        
        # Pour les prompts très longs, on les tronque pour les logs
        if data and "prompt" in data and isinstance(data["prompt"], str) and len(data["prompt"]) > 100:
            logged_data = data.copy()
            logged_data["prompt"] = f"{data['prompt'][:100]}... [tronqué, longueur totale: {len(data['prompt'])}]"
        else:
            logged_data = data
            
        logger.debug(
            f"[{request_id}] Requête {method} vers {endpoint} | "
            f"Payload: {json.dumps(logged_data) if logged_data else 'None'}"
        )
        return request_id
    
    def _log_response(self, request_id: str, endpoint: str, status_code: int, 
                     duration: float, response_data: Any) -> None:
        """Log les détails de la réponse"""
        # Tronquer les réponses très longues pour les logs
        if isinstance(response_data, dict) and "response" in response_data:
            if isinstance(response_data["response"], str) and len(response_data["response"]) > 100:
                logged_response = response_data.copy()
                logged_response["response"] = f"{response_data['response'][:100]}... [tronqué]"
            else:
                logged_response = response_data
        else:
            logged_response = response_data
            
        log_message = (
            f"[{request_id}] Réponse de {endpoint} | "
            f"Status: {status_code} | Durée: {duration:.2f}s | "
            f"Données: {json.dumps(logged_response) if logged_response else 'None'}"
        )
        
        if status_code >= 400:
            logger.error(log_message)
        else:
            logger.debug(log_message)
    
    def _make_request(self, endpoint: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Méthode générique pour effectuer des requêtes à l'API Ollama avec logging
        """
        url = f"{self.base_url}{endpoint}"
        request_id = self._log_request(endpoint, method, data)
        
        start_time = time.time()
        try:
            if method == "GET":
                response = self.client.get(url)
            elif method == "POST":
                response = self.client.post(url, json=data)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
                
            duration = time.time() - start_time
            
            response.raise_for_status()
            response_data = response.json()
            
            self._log_response(request_id, endpoint, response.status_code, duration, response_data)
            return response_data
            
        except httpx.HTTPStatusError as e:
            duration = time.time() - start_time
            logger.error(
                f"[{request_id}] Erreur HTTP {e.response.status_code} pour {endpoint} | "
                f"Durée: {duration:.2f}s | "
                f"Détails: {e.response.text}"
            )
            raise
            
        except httpx.RequestError as e:
            duration = time.time() - start_time
            logger.error(
                f"[{request_id}] Erreur de requête pour {endpoint} | "
                f"Durée: {duration:.2f}s | "
                f"Détails: {str(e)}"
            )
            raise
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des modèles disponibles
        """
        logger.info("Récupération de la liste des modèles disponibles")
        response = self._make_request("/api/tags")
        models = response.get("models", [])
        
        if models:
            model_names = [model.get("name") for model in models]
            logger.info(f"Modèles disponibles: {', '.join(model_names)}")
        else:
            logger.warning("Aucun modèle disponible")
            
        return models
    
    def generate(self, 
                prompt: str, 
                model: str = None, 
                temperature: float = 0.7,
                max_tokens: int = 1000,
                stream: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Génère du texte avec Ollama
        
        Args:
            prompt: Le texte d'entrée pour la génération
            model: Le modèle à utiliser (utilise default_model si non spécifié)
            temperature: Température pour la génération (créativité)
            max_tokens: Nombre maximum de tokens à générer
            stream: Si True, retourne un dictionnaire avec des informations supplémentaires
                   Si False, retourne directement le texte généré
        
        Returns:
            Le texte généré ou un dictionnaire avec la réponse complète
        """
        model_name = model or self.default_model
        
        logger.info(f"Génération avec modèle '{model_name}', temp={temperature}, max_tokens={max_tokens}")
        logger.debug(f"Prompt (premiers 100 car.) : {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,  # Toujours False pour l'API, stream est géré côté client
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        try:
            response = self._make_request("/api/generate", "POST", payload)
            
            generated_text = response.get("response", "")
            
            # Calcul des statistiques de réponse pour les logs
            token_count = len(generated_text.split())
            
            logger.info(
                f"Génération réussie: {token_count} tokens générés "
                f"(premiers 100 car.): {generated_text[:100]}{'...' if len(generated_text) > 100 else ''}"
            )
            
            if stream:
                return response
            else:
                return generated_text
                
        except Exception as e:
            logger.error(f"Échec de la génération avec '{model_name}': {str(e)}")
            if stream:
                return {"error": str(e), "response": ""}
            else:
                return ""
    
    def get_embeddings(self, text: str, model: str = None) -> Tuple[bool, Optional[List[float]]]:
        """
        Génère des embeddings pour un texte donné
        
        Args:
            text: Le texte pour lequel générer des embeddings
            model: Le modèle à utiliser (utilise default_model si non spécifié)
            
        Returns:
            Tuple (succès, embeddings ou None)
        """
        model_name = model or self.default_model
        
        logger.info(f"Génération d'embeddings avec modèle '{model_name}'")
        logger.debug(f"Texte (premiers 100 car.) : {text[:100]}{'...' if len(text) > 100 else ''}")
        
        payload = {
            "model": model_name,
            "prompt": text
        }
        
        try:
            response = self._make_request("/api/embeddings", "POST", payload)
            
            embeddings = response.get("embedding", [])
            
            if embeddings:
                dim = len(embeddings)
                logger.info(f"Embeddings générés avec succès: dimension={dim}")
                logger.debug(f"Quelques valeurs: {embeddings[:5]}...")
                return True, embeddings
            else:
                logger.warning("Réponse d'embedding vide")
                return False, None
                
        except Exception as e:
            logger.error(f"Échec de la génération d'embeddings: {str(e)}")
            return False, None
            
    def close(self):
        """Ferme la connexion client"""
        logger.debug("Fermeture du client Ollama")
        self.client.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Exemple d'utilisation
if __name__ == "__main__":
    # Utilisation simple
    with OllamaClient() as client:
        # Lister les modèles
        models = client.list_models()
        
        # Générer du texte
        response = client.generate(
            "Explique-moi l'importance des logs dans une application en 3 points",
            temperature=0.7,
            max_tokens=300
        )
        
        print("\nRéponse d'Ollama:")
        print("=" * 50)
        print(response)
        print("=" * 50)
        
        # Générer des embeddings
        success, embeddings = client.get_embeddings(
            "Ceci est un test d'embedding pour montrer comment utiliser les logs"
        )
        
        if success:
            print(f"\nEmbedding généré: dimension={len(embeddings)}")
            print(f"Premiers éléments: {embeddings[:5]}...")
        else:
            print("\nÉchec de la génération d'embeddings")