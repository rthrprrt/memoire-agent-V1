#!/bin/bash

echo "Attente du démarrage du backend..."
MAX_RETRIES=30
count=0

# Boucle d'attente avec timeout
while ! curl -s http://backend:8000/health > /dev/null && [ $count -lt $MAX_RETRIES ]; do
  echo "Backend pas encore prêt - tentative $((count+1))/$MAX_RETRIES - nouvelle tentative dans 3 secondes..."
  sleep 3
  count=$((count+1))
done

# Vérifier si le backend a répondu ou si nous avons atteint le nombre maximum de tentatives
if [ $count -eq $MAX_RETRIES ]; then
  echo "ATTENTION: Le backend n'est pas accessible après $MAX_RETRIES tentatives."
  echo "Tentative de démarrage du frontend quand même, mais il pourrait y avoir des problèmes de connexion."
else
  echo "Backend prêt! Démarrage du frontend..."
fi

# Démarrer Streamlit
streamlit run /app/app.py