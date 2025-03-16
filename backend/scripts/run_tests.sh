#!/bin/bash
# run_tests.sh

# Activer l'environnement virtuel si nécessaire
# source venv/bin/activate

echo "Exécution des tests unitaires..."

# Exécuter les tests avec couverture
pytest --cov=. --cov-report=term --cov-report=html

# Afficher un résumé
echo "Résumé de la couverture de code:"
echo "Consultez le rapport détaillé dans htmlcov/index.html"

# Désactiver l'environnement virtuel si nécessaire
# deactivate