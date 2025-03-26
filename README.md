# Assistant de R�daction de M�moire Professionnel

Ce projet est un assistant d'IA pour aider � la r�daction de m�moires professionnels, en offrant des fonctionnalit�s de gestion de journal de bord, organisation de sections, recherche s�mantique et int�gration avec des mod�les de langage.

## Configuration

### Variables d'environnement

- `USE_DUMMY_LLM=true` : Active le mode simul� pour les LLM (quand Ollama n'est pas disponible)
- `OLLAMA_HOST=http://localhost:11434` : URL d'Ollama (par d�faut localhost:11434)
- `OLLAMA_MODEL=mistral:7b` : Mod�le LLM par d�faut

## D�marrage de l'application

1. Backend:
```bash
cd backend
python main.py
```

2. Frontend:
```bash
cd frontend
python app.py
```

## R�solution des probl�mes

### Probl�me de thread SQLite
Si vous rencontrez l'erreur "SQLite objects created in a thread can only be used in that same thread", le code a �t� modifi� pour utiliser `check_same_thread=False`.

### Tables manquantes
Si vous rencontrez des erreurs "no such table", les d�finitions des tables manquantes ont �t� ajout�es au processus d'initialisation de la base de donn�es.

### Erreurs 404
Les erreurs 404 sont normales si vous n'avez pas encore ajout� de contenu (entr�es de journal, sections de m�moire, etc.).