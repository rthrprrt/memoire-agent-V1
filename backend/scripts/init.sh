#!/bin/bash

echo "Initializing backend application..."

# Vérifier si sentence-transformers est installé correctement
python -c "import sentence_transformers" 2>/dev/null
if [ $? -ne 0 ]; then
  echo "sentence-transformers n'est pas installé correctement."
  echo "Tentative de réinstallation..."
  pip install --no-cache-dir sentence-transformers
fi

echo "Waiting for Ollama service..."
# Attendre que le service Ollama soit disponible
max_retries=30
count=0
while ! curl -s http://ollama:11434/api/tags > /dev/null && [ $count -lt $max_retries ]; do
  echo "Checking Ollama service at http://ollama:11434... (attempt $((count+1))/$max_retries)"
  sleep 2
  count=$((count+1))
done

if [ $count -eq $max_retries ]; then
  echo "WARNING: Ollama service not available after $max_retries attempts."
  echo "The application will start, but AI functionalities may be limited."
else
  echo "Ollama service is available."
  
  # Check if required models are available
  echo "Checking required models..."
  models=("llama3:8b" "mistral:7b" "nomic-embed-text")
  
  for model in "${models[@]}"; do
    curl -s http://ollama:11434/api/tags | grep -q "$model"
    if [ $? -ne 0 ]; then
      echo "Pulling model $model..."
      curl -X POST http://ollama:11434/api/pull -d "{\"model\":\"$model\"}" &
      # Don't wait for the pull to complete, continue in background
    else
      echo "Model $model is already available."
    fi
  done
fi

echo "Initializing database..."
# Si le drapeau RESET_DB est activé, supprimer la base de données existante
if [ "$RESET_DB" = "true" ]; then
  echo "Resetting database as per RESET_DB flag..."
  if [ -f /app/data/memoire.db ]; then
    rm /app/data/memoire.db
    echo "Existing database removed."
  fi
  # Supprimer également les données vectorielles de ChromaDB
  if [ -d /app/data/chromadb ]; then
    rm -rf /app/data/chromadb
    echo "Existing ChromaDB data removed."
  fi
fi

# Créer les répertoires nécessaires s'ils n'existent pas
mkdir -p /app/data/chromadb
mkdir -p /app/logs

echo "Starting FastAPI application..."
# Lancer l'application FastAPI avec uvicorn
cd /app && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload