# Configuration de Logging pour l'Assistant Mémoire

Ce document décrit la configuration de logging mise en place pour l'application Assistant Mémoire, qui utilise Rich et Loguru pour améliorer la présentation et la gestion des logs.

## Fonctionnalités de Logging

- **Logs colorés et formatés** avec Rich pour une meilleure lisibilité dans la console
- **Gestion avancée des logs** avec Loguru
- **Rotation des fichiers de logs** par date/heure
- **Niveaux de logs différents** (DEBUG, INFO, WARNING, ERROR)
- **Tracebacks améliorés** avec Rich pour mieux déboguer les erreurs
- **Dégradation gracieuse** si les librairies optionnelles ne sont pas disponibles

## Utilisation dans le Code

### Backend (FastAPI)

```python
# Dans les modules du backend
from core.logging_config import get_logger

# Obtenir un logger pour le module actuel
logger = get_logger(__name__)

# Utiliser le logger
logger.debug("Message de débogage détaillé")
logger.info("Information standard")
logger.warning("Avertissement")
logger.error("Erreur")
logger.exception("Exception avec traceback")
```

### Frontend (Streamlit)

```python
# Dans les modules du frontend
from utils.logging_config import get_logger

# Obtenir un logger pour le module actuel
logger = get_logger(__name__)

# Utiliser le logger
logger.debug("Message de débogage détaillé")
logger.info("Information standard")
logger.warning("Avertissement")
logger.error("Erreur")
```

## Configuration

Les paramètres de logging peuvent être configurés via les variables d'environnement suivantes :

- `LOG_LEVEL` : Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL). Par défaut : INFO
- `LOG_FILE` : Chemin du fichier de log. Par défaut : logs/api.log (backend) ou logs/frontend.log (frontend)

## Emplacement des Fichiers de Logs

- **Backend** : `backend/logs/api_YYYYMMDD_HHMMSS.log`
- **Frontend** : `frontend/logs/frontend_YYYYMMDD_HHMMSS.log`

## Installation des Dépendances

Les dépendances suivantes sont requises pour profiter pleinement du système de logging amélioré :

```bash
# Pour le backend
pip install rich loguru

# Pour le frontend
pip install rich loguru
```

Si ces librairies ne sont pas disponibles, le système se dégrade gracieusement vers le logging standard de Python.

## Visualisation des Logs

### Console

Avec Rich installé, les logs dans la console seront colorés et formatés pour une meilleure lisibilité :

- **DEBUG** : Bleu
- **INFO** : Vert
- **WARNING** : Jaune
- **ERROR** : Rouge
- **CRITICAL** : Rouge sur fond blanc

### Interface Streamlit

L'application Streamlit dispose d'une page de diagnostic qui permet de visualiser les logs récents et de télécharger les fichiers de logs complets.