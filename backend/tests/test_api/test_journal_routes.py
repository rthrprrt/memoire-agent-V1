# tests/test_api/test_journal_routes.py
import pytest
from fastapi.testclient import TestClient
from datetime import datetime

def test_get_journal_entries(test_client):
    # Récupérer les entrées du journal
    response = test_client.get("/journal/entries")
    
    # Vérifier que la requête a réussi
    assert response.status_code == 200
    
    # Vérifier que la réponse est une liste (même vide au départ)
    assert isinstance(response.json(), list)

def test_add_journal_entry(test_client):
    # Créer une entrée de journal
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Test entry via API",
        "type_entree": "test",
        "tags": ["test", "api"]
    }
    
    # Ajouter l'entrée
    response = test_client.post("/journal/entries", json=entry_data)
    
    # Vérifier que la requête a réussi
    assert response.status_code == 200
    
    # Vérifier que l'entrée a été ajoutée correctement
    result = response.json()
    assert "id" in result
    assert result["content"] == entry_data["texte"]
    assert result["type_entree"] == entry_data["type_entree"]
    assert set(result["tags"]) == set(entry_data["tags"])
    
    # Récupérer l'entrée pour vérifier qu'elle existe bien
    entry_id = result["id"]
    response = test_client.get(f"/journal/entries/{entry_id}")
    
    # Vérifier que l'entrée est récupérée correctement
    assert response.status_code == 200
    assert response.json()["id"] == entry_id

def test_update_journal_entry(test_client):
    # Créer une entrée de journal
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entry to be updated",
        "type_entree": "test"
    }
    
    # Ajouter l'entrée
    response = test_client.post("/journal/entries", json=entry_data)
    entry_id = response.json()["id"]
    
    # Mettre à jour l'entrée
    update_data = {
        "texte": "Updated entry",
        "tags": ["updated"]
    }
    
    response = test_client.put(f"/journal/entries/{entry_id}", json=update_data)
    
    # Vérifier que la mise à jour a réussi
    assert response.status_code == 200
    
    # Vérifier que l'entrée a été mise à jour correctement
    result = response.json()
    assert result["id"] == entry_id
    assert result["content"] == update_data["texte"]
    assert set(result["tags"]) == set(update_data["tags"])

def test_delete_journal_entry(test_client):
    # Créer une entrée de journal
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entry to be deleted",
        "type_entree": "test"
    }
    
    # Ajouter l'entrée
    response = test_client.post("/journal/entries", json=entry_data)
    entry_id = response.json()["id"]
    
    # Supprimer l'entrée
    response = test_client.delete(f"/journal/entries/{entry_id}")
    
    # Vérifier que la suppression a réussi
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Vérifier que l'entrée n'existe plus
    response = test_client.get(f"/journal/entries/{entry_id}")
    assert response.status_code == 404