#!/usr/bin/env python
"""
Script de test pour la connexion à Ollama
Ce script vérifie si Ollama est en cours d'exécution et répond correctement aux requêtes.
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Any, Optional, List, Tuple

# Configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "mistral:7b")
TIMEOUT = 10  # secondes

# Configuration du logging
try:
    from core.logging_config import get_logger
    logger = get_logger("ollama_test")
except ImportError:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("ollama_test")

def test_ollama_health() -> bool:
    """
    Vérifie si le serveur Ollama répond à une requête simple
    """
    try:
        logger.info(f"Tentative de connexion à Ollama sur {OLLAMA_BASE_URL}")
        response = requests.get(f"{OLLAMA_BASE_URL}", timeout=TIMEOUT)
        if response.status_code == 200:
            logger.info("✅ Ollama est en ligne et répond")
            return True
        else:
            logger.warning(f"❌ Ollama a répondu avec le code d'état {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erreur de connexion à Ollama: {str(e)}")
        return False

def get_available_models() -> List[Dict[str, Any]]:
    """
    Récupère la liste des modèles disponibles sur Ollama
    """
    try:
        logger.info("Récupération des modèles disponibles")
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=TIMEOUT)
        response.raise_for_status()
        models = response.json().get("models", [])
        
        if models:
            logger.info(f"✅ {len(models)} modèles trouvés sur Ollama")
            return models
        else:
            logger.warning("❌ Aucun modèle trouvé sur Ollama")
            return []
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erreur lors de la récupération des modèles: {str(e)}")
        return []

def test_model_generation(model_name: str = DEFAULT_MODEL) -> Tuple[bool, Optional[str]]:
    """
    Teste la génération de texte avec un modèle spécifique
    """
    prompt = "Explique-moi l'importance de la documentation dans un projet informatique en une phrase."
    
    try:
        logger.info(f"Test de génération avec le modèle '{model_name}'")
        start_time = time.time()
        
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 100,  # Limiter la longueur de la réponse
                    "temperature": 0.7
                }
            },
            timeout=30  # Temps d'attente plus long pour la génération
        )
        
        response.raise_for_status()
        elapsed = time.time() - start_time
        
        result = response.json()
        generated_text = result.get("response", "")
        
        if generated_text:
            logger.info(f"✅ Génération réussie en {elapsed:.2f}s")
            logger.info(f"Réponse: {generated_text}")
            return True, generated_text
        else:
            logger.warning("❌ Génération vide")
            return False, None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erreur lors de la génération: {str(e)}")
        return False, None

def test_ollama_embeddings(model_name: str = DEFAULT_MODEL) -> Tuple[bool, Optional[List[float]]]:
    """
    Teste la génération d'embeddings avec Ollama
    """
    text = "Ceci est un test d'embedding pour vérifier la fonctionnalité d'Ollama"
    
    try:
        logger.info(f"Test d'embeddings avec le modèle '{model_name}'")
        
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": model_name,
                "prompt": text
            },
            timeout=TIMEOUT
        )
        
        response.raise_for_status()
        result = response.json()
        
        embeddings = result.get("embedding", [])
        
        if embeddings and len(embeddings) > 0:
            embedding_length = len(embeddings)
            logger.info(f"✅ Embeddings générés avec succès: vecteur de dimension {embedding_length}")
            # Afficher les 5 premières valeurs
            logger.info(f"Échantillon: {embeddings[:5]}...")
            return True, embeddings
        else:
            logger.warning("❌ Échec de génération d'embeddings")
            return False, None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Erreur lors de la génération d'embeddings: {str(e)}")
        return False, None

def run_all_tests():
    """
    Exécute tous les tests d'Ollama et affiche un résumé
    """
    logger.info("=" * 50)
    logger.info("TESTS DE CONNEXION À OLLAMA")
    logger.info("=" * 50)
    
    results = {
        "health": False,
        "models_available": False,
        "text_generation": False,
        "embeddings": False
    }
    
    # Test 1: Vérification que Ollama est en ligne
    results["health"] = test_ollama_health()
    
    if not results["health"]:
        logger.error("❌ Impossible de se connecter à Ollama. Vérifiez qu'il est bien en cours d'exécution.")
        return results
    
    # Test 2: Récupération des modèles disponibles
    models = get_available_models()
    results["models_available"] = len(models) > 0
    
    if results["models_available"]:
        logger.info("Modèles disponibles:")
        for model in models:
            name = model.get("name", "Inconnu")
            modified = model.get("modified", "date inconnue")
            size = model.get("size", 0) / (1024 * 1024 * 1024)  # Convertir en GB
            logger.info(f"  - {name} ({size:.2f} GB) [modifié: {modified}]")
    
    # Test 3: Vérification que le modèle par défaut est disponible
    model_names = [model.get("name") for model in models]
    if DEFAULT_MODEL not in model_names:
        logger.warning(f"⚠️ Le modèle par défaut '{DEFAULT_MODEL}' n'est pas disponible sur Ollama")
        logger.warning(f"⚠️ Utilisez 'ollama pull {DEFAULT_MODEL}' pour le télécharger")
        
        # Si au moins un modèle est disponible, on l'utilise pour les tests suivants
        if model_names:
            test_model = model_names[0]
            logger.info(f"Utilisation du modèle '{test_model}' pour les tests")
        else:
            logger.error("❌ Aucun modèle disponible pour les tests")
            return results
    else:
        test_model = DEFAULT_MODEL
    
    # Test 4: Génération de texte
    results["text_generation"], _ = test_model_generation(test_model)
    
    # Test 5: Génération d'embeddings
    results["embeddings"], _ = test_ollama_embeddings(test_model)
    
    # Affichage du résumé
    logger.info("=" * 50)
    logger.info("RÉSUMÉ DES TESTS")
    logger.info("=" * 50)
    logger.info(f"Connexion à Ollama: {'✅ OK' if results['health'] else '❌ ÉCHEC'}")
    logger.info(f"Modèles disponibles: {'✅ OK' if results['models_available'] else '❌ ÉCHEC'}")
    logger.info(f"Génération de texte: {'✅ OK' if results['text_generation'] else '❌ ÉCHEC'}")
    logger.info(f"Génération d'embeddings: {'✅ OK' if results['embeddings'] else '❌ ÉCHEC'}")
    
    all_passed = all(results.values())
    logger.info("=" * 50)
    if all_passed:
        logger.info("✅ TOUS LES TESTS ONT RÉUSSI")
    else:
        logger.warning("⚠️ CERTAINS TESTS ONT ÉCHOUÉ")
    logger.info("=" * 50)
    
    return results

if __name__ == "__main__":
    run_all_tests()