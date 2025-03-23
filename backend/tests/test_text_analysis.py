import sys
import os
import pytest
from pathlib import Path

# Ajouter le répertoire racine au chemin Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Tester les deux chemins d'import possibles
try:
    from utils.text_analysis import extract_automatic_tags as utils_extract_tags
    utils_import_works = True
except ImportError:
    utils_import_works = False

try:
    from api.utils.text_analysis import extract_automatic_tags as api_extract_tags
    api_import_works = True
except ImportError:
    api_import_works = False


def test_text_analysis_functions_exist():
    """Test que au moins une des fonctions d'extraction existe"""
    assert utils_import_works or api_import_works, "Aucune fonction extract_automatic_tags n'a pu être importée"


@pytest.mark.skipif(not utils_import_works, reason="utils.text_analysis n'est pas importable")
def test_utils_extract_tags():
    """Test la fonction extract_automatic_tags de utils.text_analysis"""
    text = "Le chat noir et blanc saute sur la table. Le chat mange sa pâtée."
    tags = utils_extract_tags(text)
    
    assert isinstance(tags, list), "La fonction doit retourner une liste"
    assert len(tags) <= 5, "La fonction ne doit pas retourner plus de 5 tags"
    
    # Vérifier que 'chat' est dans les tags car c'est répété deux fois
    assert "chat" in tags, "Le mot 'chat' devrait être présent dans les tags"


@pytest.mark.skipif(not api_import_works, reason="api.utils.text_analysis n'est pas importable")
def test_api_extract_tags():
    """Test la fonction extract_automatic_tags de api.utils.text_analysis"""
    text = "Le chat noir et blanc saute sur la table. Le chat mange sa pâtée."
    tags = api_extract_tags(text)
    
    assert isinstance(tags, list), "La fonction doit retourner une liste"
    assert len(tags) <= 5, "La fonction ne doit pas retourner plus de 5 tags"
    
    # Vérifier que 'chat' est dans les tags car c'est répété deux fois
    assert "chat" in tags, "Le mot 'chat' devrait être présent dans les tags"