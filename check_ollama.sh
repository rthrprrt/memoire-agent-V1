#!/bin/bash

# Couleurs pour le terminal
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "============================================="
echo "VERIFICATION DU PROCESSUS OLLAMA"
echo "============================================="

# Vérifier si le processus Ollama est en cours d'exécution
if pgrep -x "ollama" > /dev/null; then
    echo -e "${GREEN}OK: Ollama est en cours d'exécution${NC}"
else
    echo -e "${RED}ERREUR: Ollama n'est pas en cours d'exécution${NC}"
    echo -e "${RED}Veuillez démarrer Ollama avec la commande: ollama serve${NC}"
fi

# Vérifier si le port 11434 est en écoute
if netstat -tuln | grep -q ":11434 "; then
    echo -e "${GREEN}OK: Le port 11434 est en écoute${NC}"
else
    echo -e "${RED}ERREUR: Le port 11434 n'est pas en écoute${NC}"
    echo -e "${RED}Ollama est peut-être en cours de démarrage ou utilise un port différent${NC}"
fi

# Ping sur l'API Ollama
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:11434)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}OK: L'API Ollama répond (code HTTP 200)${NC}"
else
    echo -e "${RED}ERREUR: L'API Ollama ne répond pas correctement (code HTTP $HTTP_CODE)${NC}"
fi

# Vérifier l'installation d'Ollama
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}OK: Ollama est installé${NC}"
    echo
    echo -e "${CYAN}Modèles disponibles:${NC}"
    ollama list
else
    echo -e "${RED}ERREUR: Ollama n'est pas installé ou n'est pas dans le PATH${NC}"
    echo -e "${RED}Installation: https://ollama.com/download${NC}"
fi

echo
echo "============================================="
echo "Pour tester l'intégration avec votre application:"
echo "cd backend"
echo "python test_ollama.py"
echo "============================================="