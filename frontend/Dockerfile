FROM python:3.9-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer le répertoire des scripts
RUN mkdir -p /app/scripts

# Copier le script d'attente
COPY scripts/wait-for-backend.sh /app/scripts/wait-for-backend.sh
RUN chmod +x /app/scripts/wait-for-backend.sh

# Mettre à jour pip
RUN pip install --upgrade pip

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copier les fichiers de l'application
COPY . .

# Exposer le port
EXPOSE 8501

# Commande pour démarrer l'application
CMD ["/app/scripts/wait-for-backend.sh"]