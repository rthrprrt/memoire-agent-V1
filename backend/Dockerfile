FROM python:3.9-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements.txt en premier pour utiliser le cache Docker
COPY requirements.txt .

# Installer les dépendances Python par groupes pour mieux gérer les timeouts
# Installer d'abord les dépendances de base (plus rapides)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout 300 \
    fastapi==0.103.1 \
    uvicorn==0.23.2 \
    httpx==0.25.0 \
    pydantic==2.3.0 \
    python-multipart==0.0.6 \
    sqlalchemy==2.0.20 \
    websockets==11.0.3 \
    python-dotenv==1.0.0 \
    loguru==0.7.0 \
    aiofiles==23.2.1 \
    tenacity==8.2.3

# Installer les dépendances liées aux documents et PDF
RUN pip install --no-cache-dir --timeout 300 \
    PyPDF2==3.0.1 \
    pdfminer.six==20221105 \
    reportlab==3.6.12 \
    python-docx==0.8.11 \
    pillow==10.0.0

# Installer les dépendances scientifiques
RUN pip install --no-cache-dir --timeout 300 \
    matplotlib==3.7.2 \
    numpy==1.25.2

# Installer les dépendances d'IA et de LLM avec un timeout plus long
RUN pip install --no-cache-dir --timeout 600 \
    langchain==0.0.267 \
    chromadb==0.4.15 \
    tiktoken==0.5.1 \
    huggingface-hub==0.16.4

# Installer sentence-transformers séparément avec un timeout encore plus long
# et continuer même en cas d'échec
RUN pip install --no-cache-dir --timeout 900 --retries 3 \
    sentence-transformers==2.2.2 || \
    echo "Warning: sentence-transformers installation failed, but continuing build"

# Créer les répertoires nécessaires
RUN mkdir -p /app/data /app/logs /app/scripts

# Copier le reste du code
COPY . .

# S'assurer que les scripts sont exécutables
RUN mkdir -p /app/scripts && \
    if [ -f /app/scripts/init.sh ]; then chmod +x /app/scripts/init.sh; fi

# Exposer le port 8000
EXPOSE 8000

# Définir la commande par défaut
CMD ["sh", "-c", "if [ -f /app/scripts/init.sh ]; then /app/scripts/init.sh; else uvicorn main:app --host 0.0.0.0 --port 8000; fi"]