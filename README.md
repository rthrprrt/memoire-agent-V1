# Assistant de Rédaction de Mémoire Professionnel

Ce projet est un assistant d'IA pour aider à la rédaction de mémoires professionnels, en offrant des fonctionnalités de gestion de journal de bord, organisation de sections, recherche sémantique et intégration avec des modèles de langage.

## Architecture et Responsabilités

### Structure du Projet

```
memoire-agent/
├── backend/               # Serveur API FastAPI
│   ├── api/               # Définitions API (routes, modèles)
│   ├── core/              # Configuration et services centraux
│   ├── db/                # Modèles et accès base de données
│   ├── services/          # Services métier
│   └── utils/             # Utilitaires
├── frontend/              # Interface utilisateur Streamlit
│   ├── app.py             # Point d'entrée de l'interface
│   └── utils/             # Utilitaires frontend
├── backups/               # Sauvegardes automatiques
└── logs/                  # Journaux d'application
```

### Composants Principaux

#### Backend

- **main.py**: Point d'entrée du serveur backend FastAPI
- **api/routes/**: Définition des endpoints API
  - **journal.py**: Routes pour la gestion du journal de bord
  - **memoire.py**: Routes pour la gestion du mémoire
  - **search.py**: Routes pour la recherche sémantique
  - **ai.py**: Routes pour l'intégration des LLM
  - **export.py**: Routes pour l'exportation de contenu
  - **hallucination.py**: Routes pour la détection d'hallucinations
  - **admin.py**: Routes administratives (cleanup, maintenance)

- **api/models/**: Schémas Pydantic pour validation des requêtes/réponses
  - Chaque fichier correspond aux modèles des routes correspondantes

- **db/models/db_models.py**: Définitions des modèles SQLAlchemy
  - Tables pour le journal, le mémoire, les tags, etc.

- **db/repositories/**: Accès aux données
  - **journal_repository.py**: Opérations CRUD pour entrées journal
  - **memoire_repository.py**: Opérations CRUD pour sections mémoire

- **services/**: Logique métier
  - **memory_service.py**: Service de gestion des entrées et sections
  - **llm_service.py**: Service d'intégration avec modèles LLM (via Ollama)
  - **export_service.py**: Génération de documents exportables

- **utils/**: Fonctions utilitaires
  - **text_processing.py**: Traitement de texte et NLP
  - **pdf_extractor.py**: Extraction de contenu depuis PDFs
    - Responsable de l'extraction de dates et tags
  - **text_analysis.py**: Analyse de texte (extraction d'entités, etc.)
  - **circuit_breaker.py**: Protection contre les pannes externes

#### Frontend

- **app.py**: Application Streamlit principale
  - Définit toutes les pages et visualisations
  - Gère l'affichage du tableau de bord, journal, mémoire
  - Coordonne les interactions avec l'API backend

- **utils/logging_config.py**: Configuration de logging pour frontend

### Mécanismes Clés

- **Extraction de dates et tags**: Le système extrait intelligemment les dates à partir des noms de fichiers ou du contenu lors de l'importation de documents (backend/utils/pdf_extractor.py)
- **Base de données vectorielle**: Permet la recherche sémantique (backend/core/memory_manager.py)
- **Intégration LLM**: Communication avec Ollama pour génération de texte (backend/services/llm_service.py)
- **Système de backup**: Sauvegarde automatique des données et sessions (backend/backup_manager.py)

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

### Intégration avec Ollama

L'application peut utiliser Ollama pour les fonctionnalités d'IA. Voir [OLLAMA.md](OLLAMA.md) pour plus de détails sur la configuration et l'utilisation.

## Roadmap

### Phase 1: Fondations (Actuel)
- ✅ Journal de bord avec importation de documents
- ✅ Extraction automatique de dates et tags
- ✅ Tableau de bord avec visualisations
- ✅ Système de sauvegarde automatique
- ✅ Intégration LLM basique avec Ollama

### Phase 2: Rédaction Assistée (En cours)
- 🔄 Génération de suggestions de sections du mémoire
- 🔄 Rédaction assistée par IA de paragraphes
- ⬜ Détection avancée d'hallucinations
- ⬜ Analyses de sentiment et thématiques des entrées journal

### Phase 3: Collaboration et Production (Planifié)
- ⬜ Exportation vers différents formats (Word, PDF, Markdown)
- ⬜ Collaboration multi-utilisateurs
- ⬜ Suggestions automatiques de citations et références
- ⬜ Visualisations avancées de progression
- ⬜ Intégration d'un correcteur orthographique et grammatical

### Phase 4: Intelligence Avancée (Vision)
- ⬜ Réponses contextuelles basées sur l'ensemble du mémoire
- ⬜ Suggestions de restructuration basées sur la cohérence
- ⬜ Analyse comparative avec d'autres mémoires (anonymisés)
- ⬜ Détection de plagiats et suggestions d'originalité

## Résolution des problèmes

### Problème de thread SQLite
Si vous rencontrez l'erreur "SQLite objects created in a thread can only be used in that same thread", le code a été modifié pour utiliser `check_same_thread=False`.

### Tables manquantes
Si vous rencontrez des erreurs "no such table", les définitions des tables manquantes ont été ajoutées au processus d'initialisation de la base de données.

### Erreurs 404
Les erreurs 404 sont normales si vous n'avez pas encore ajouté de contenu (entrées de journal, sections de mémoire, etc.).

### Problèmes connus avec les tags
Si vous rencontrez des problèmes avec l'affichage des tags ou des erreurs JavaScript dans le tableau de bord, utilisez les outils de nettoyage:
- Route API: `/admin/cleanup/orphan-tags` pour supprimer les tags orphelins
- Route API: `/admin/cleanup/import-tags` pour supprimer les tags liés aux imports

### Logs
Si vous rencontrez des problèmes, consultez les logs dans les répertoires suivants :
- Backend : `backend/logs/`
- Frontend : `frontend/logs/`

La page "Diagnostic" de l'interface Streamlit permet également de visualiser les logs récents.