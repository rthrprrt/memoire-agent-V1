# Assistant de Rédaction de Mémoire Professionnel

Ce projet est un assistant d'IA pour aider à la rédaction de mémoires professionnels, en offrant des fonctionnalités de gestion de journal de bord, organisation de sections, recherche sémantique et intégration avec des modèles de langage.

## Configuration

### Variables d'environnement

- `USE_DUMMY_LLM=true` : Active le mode simulé pour les LLM (quand Ollama n'est pas disponible)
- `OLLAMA_HOST=http://localhost:11434` : URL d'Ollama (par défaut localhost:11434)
- `OLLAMA_MODEL=mistral:7b` : Modèle LLM par défaut
- `LOG_LEVEL` : Niveau de log (DEBUG, INFO, WARNING, ERROR). Par défaut : INFO
- `LOG_FILE` : Chemin du fichier de log. Configuration optionnelle, par défaut dans le dossier `logs`

## Démarrage de l'application

1. Backend:
```bash
cd backend
python main.py
```

2. Frontend:
```bash
cd frontend
streamlit run app.py
```

## Fonctionnalités

### Système de logging amélioré

L'application dispose d'un système de logging amélioré utilisant Rich et Loguru pour une meilleure expérience de débogage :

- Logs colorés et formatés dans la console
- Tracebacks améliorés pour faciliter l'identification des erreurs
- Rotation des fichiers de logs par date/heure
- Configuration unifiée entre backend et frontend

Pour plus de détails, consultez le fichier [LOGGING.md](LOGGING.md).

## Résolution des problèmes

### Problème de thread SQLite
Si vous rencontrez l'erreur "SQLite objects created in a thread can only be used in that same thread", le code a été modifié pour utiliser `check_same_thread=False`.

### Tables manquantes
Si vous rencontrez des erreurs "no such table", les définitions des tables manquantes ont été ajoutées au processus d'initialisation de la base de données.

### Erreurs 404
Les erreurs 404 sont normales si vous n'avez pas encore ajouté de contenu (entrées de journal, sections de mémoire, etc.).

### Logs
Si vous rencontrez des problèmes, consultez les logs dans les répertoires suivants :
- Backend : `backend/logs/`
- Frontend : `frontend/logs/`

La page "Diagnostic" de l'interface Streamlit permet également de visualiser les logs récents.
