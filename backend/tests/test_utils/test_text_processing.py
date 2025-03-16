# tests/test_utils/test_text_processing.py
import pytest
from utils.text_processing import AdaptiveTextSplitter, extract_automatic_tags

def test_adaptive_text_splitter():
    # Instancier le splitter
    splitter = AdaptiveTextSplitter()
    
    # Tester avec différents types de contenu
    long_text = "This is a long paragraph that should be considered as long form text. " * 10
    list_text = "List items:\n- Item 1\n- Item 2\n- Item 3"
    technical_text = "function test() {\n  return 'This is a technical content';\n}"
    
    # Vérifier la détection du type de contenu
    assert splitter._determine_content_type(long_text) == "long_form"
    assert splitter._determine_content_type(list_text) == "list"
    assert splitter._determine_content_type(technical_text) == "technical"
    
    # Vérifier la découpe du texte
    long_chunks = splitter.split_text(long_text)
    assert len(long_chunks) > 0
    
    list_chunks = splitter.split_text(list_text)
    assert len(list_chunks) > 0
    
    tech_chunks = splitter.split_text(technical_text)
    assert len(tech_chunks) > 0
    
    # Vérifier que la découpe respecte les limites de taille
    for chunk in long_chunks:
        assert len(chunk) <= 800  # chunk_size max pour le type long_form

def test_extract_automatic_tags():
    # Tester l'extraction de tags à partir de textes
    technical_text = "Python programming with FastAPI and SQLite for database management."
    tags = extract_automatic_tags(technical_text)
    
    # Vérifier que des tags pertinents sont extraits
    assert len(tags) > 0
    assert any(tag in ["python", "programming", "fastapi", "sqlite", "database", "management"] for tag in tags)
    
    # Tester l'extraction avec un texte vide
    empty_tags = extract_automatic_tags("")
    assert len(empty_tags) == 0
    
    # Tester l'extraction avec un texte très court
    short_tags = extract_automatic_tags("Short text")
    assert len(short_tags) <= 1
    
    # Tester l'extraction avec un seuil personnalisé
    high_threshold_tags = extract_automatic_tags(technical_text, threshold=0.5)
    assert len(high_threshold_tags) <= len(tags)