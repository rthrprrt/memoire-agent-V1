# Outils de diagnostic et d'intégration Ollama

Ce document explique comment utiliser les outils fournis pour tester la configuration d'Ollama avec votre application Assistant Mémoire.

## Prérequis

1. Ollama installé sur votre machine (téléchargement : [https://ollama.com/download](https://ollama.com/download))
2. Au moins un modèle téléchargé dans Ollama (ex: `ollama pull mistral:7b`)
3. Python 3.10+ avec les bibliothèques requises

## Installation des dépendances

Activez votre environnement conda pour le backend :

```bash
conda activate memoire-backend
pip install psutil requests httpx
```

## Outils disponibles

### 1. Test de connexion Ollama

Le script `test_ollama.py` vérifie si Ollama est en cours d'exécution et répond correctement :

```bash
cd backend
python test_ollama.py
```

Ce script effectue les tests suivants :
- Vérification que Ollama est accessible
- Récupération de la liste des modèles disponibles
- Test de génération de texte
- Test de génération d'embeddings

### 2. Vérification du processus Ollama (Windows)

Exécutez le script batch pour vérifier si Ollama est en cours d'exécution :

```batch
check_ollama.bat
```

### 3. Vérification du processus Ollama (Linux/macOS)

```bash
chmod +x check_ollama.sh
./check_ollama.sh
```

### 4. Diagnostic complet d'Ollama

Pour un diagnostic détaillé des problèmes potentiels :

```bash
cd backend
python diagnose_ollama.py
```

Ce script vérifie :
- L'état du processus Ollama
- Les connexions réseau et ports
- Les ressources système (CPU, RAM, GPU)
- Les modèles disponibles
- L'accessibilité des endpoints API

## Exemple d'intégration avec logs

Le fichier `examples/ollama_logger_example.py` montre comment intégrer des logs détaillés dans vos interactions avec Ollama :

```bash
cd backend
python examples/ollama_logger_example.py
```

## Configuration d'Ollama

### Variables d'environnement

Vous pouvez configurer Ollama via les variables d'environnement suivantes :

- `OLLAMA_HOST` : URL de l'API Ollama (défaut : `http://localhost:11434`)
- `OLLAMA_MODEL` : Modèle à utiliser par défaut (défaut : `mistral:7b`)

### Commandes Ollama utiles

```bash
# Démarrer le serveur Ollama
ollama serve

# Lister les modèles disponibles
ollama list

# Télécharger un modèle
ollama pull mistral:7b

# Supprimer un modèle
ollama rm <nom-du-modèle>
```

## Intégration dans votre code

Exemple d'intégration dans votre code d'application :

```python
from core.logging_config import get_logger
import requests
import time

logger = get_logger("ollama_client")

def generate_text(prompt, model="mistral:7b"):
    """Génère du texte avec Ollama et inclut des logs pertinents"""
    logger.info(f"Génération de texte avec le modèle {model}")
    logger.debug(f"Prompt: {prompt[:100]}...")
    
    start_time = time.time()
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 500}
            },
            timeout=30
        )
        
        response.raise_for_status()
        elapsed = time.time() - start_time
        
        result = response.json()
        generated_text = result.get("response", "")
        
        logger.info(f"Génération réussie en {elapsed:.2f}s - {len(generated_text)} caractères générés")
        return generated_text
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération: {str(e)}")
        return None
```

## Résolution des problèmes courants

### Ollama ne démarre pas

Vérifiez si un autre processus utilise le port 11434 :
- Windows : `netstat -ano | findstr :11434`
- Linux/macOS : `lsof -i :11434`

### Erreurs de mémoire insuffisante

Ollama nécessite de la mémoire pour charger les modèles :
- Utilisez des modèles plus petits (7B au lieu de 13B)
- Fermez d'autres applications gourmandes en mémoire
- Augmentez la RAM de votre système

### Erreurs de connexion refusée

- Vérifiez que Ollama est démarré (`ollama serve`)
- Vérifiez que l'URL d'Ollama est correcte dans votre configuration

### Erreurs de timeout

- Augmentez la valeur de timeout dans vos requêtes API
- Vérifiez si votre système a suffisamment de ressources

### Modèle non trouvé

Utilisez `ollama list` pour vérifier les modèles disponibles, puis téléchargez le modèle manquant avec `ollama pull <nom-du-modèle>`