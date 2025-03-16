# tests/test_api/test_journal.py
import pytest
from fastapi.testclient import TestClient
from datetime import datetime

@pytest.mark.asyncio
async def test_add_journal_entry(client):
    """Test l'ajout d'une entrée de journal via l'API"""
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Test d'ajout d'entrée via l'API",
        "type_entree": "test",
        "tags": ["api", "test"]
    }
    
    response = client.post("/journal/entries", json=entry_data)
    
    assert response.status_code == 200
    result = response.json()
    assert "id" in result
    assert result["content"] == entry_data["texte"]
    assert set(result["tags"]) == set(entry_data["tags"])

@pytest.mark.asyncio
async def test_get_journal_entries(client):
    """Test la récupération des entrées de journal via l'API"""
    # Ajouter une entrée pour le test
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entrée pour tester la récupération",
        "type_entree": "test"
    }
    
    client.post("/journal/entries", json=entry_data)
    
    # Récupérer les entrées
    response = client.get("/journal/entries")
    
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) > 0

@pytest.mark.asyncio
async def test_get_journal_entry(client):
    """Test la récupération d'une entrée spécifique de journal"""
    # Ajouter une entrée pour le test
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entrée individuelle à récupérer",
        "type_entree": "test"
    }
    
    response = client.post("/journal/entries", json=entry_data)
    entry_id = response.json()["id"]
    
    # Récupérer l'entrée spécifique
    response = client.get(f"/journal/entries/{entry_id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == entry_id
    assert result["content"] == entry_data["texte"]

@pytest.mark.asyncio
async def test_update_journal_entry(client):
    """Test la mise à jour d'une entrée de journal"""
    # Ajouter une entrée pour le test
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entrée à mettre à jour via API",
        "type_entree": "test"
    }
    
    response = client.post("/journal/entries", json=entry_data)
    entry_id = response.json()["id"]
    
    # Mettre à jour l'entrée
    update_data = {
        "texte": "Entrée mise à jour via API",
        "tags": ["updated", "api"]
    }
    
    response = client.put(f"/journal/entries/{entry_id}", json=update_data)
    
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == entry_id
    assert result["content"] == update_data["texte"]
    assert set(result["tags"]) == set(update_data["tags"])

@pytest.mark.asyncio
async def test_delete_journal_entry(client):
    """Test la suppression d'une entrée de journal"""
    # Ajouter une entrée pour le test
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entrée à supprimer via API",
        "type_entree": "test"
    }
    
    response = client.post("/journal/entries", json=entry_data)
    entry_id = response.json()["id"]
    
    # Supprimer l'entrée
    response = client.delete(f"/journal/entries/{entry_id}")
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "success"
    
    # Vérifier que l'entrée n'est plus accessible
    response = client.get(f"/journal/entries/{entry_id}")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_search_journal_entries(client):
    """Test la recherche d'entrées de journal"""
    # Ajouter des entrées avec du contenu spécifique
    entries = [
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "texte": "Recherche de solutions pour améliorer l'architecture",
            "type_entree": "projet"
        },
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "texte": "Session de travail sur l'optimisation des performances",
            "type_entree": "projet"
        }
    ]
    
    for entry in entries:
        client.post("/journal/entries", json=entry)
    
    # Effectuer une recherche
    response = client.get("/search?query=architecture")
    
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0