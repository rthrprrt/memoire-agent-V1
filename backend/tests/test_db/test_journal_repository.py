# tests/test_db/test_journal_repository.py
import pytest
from datetime import datetime

@pytest.mark.asyncio
async def test_add_entry(mock_journal_repository):
    # Créer une entrée de test
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Test entry for unit testing",
        "type_entree": "test",
        "tags": ["test", "unit"]
    }
    
    # Appeler la méthode add_entry
    result = await mock_journal_repository.add_entry(entry_data)
    
    # Vérifier que l'entrée a été ajoutée
    assert result is not None
    assert "id" in result
    assert result["content"] == entry_data["texte"]
    assert result["type_entree"] == entry_data["type_entree"]
    assert set(result["tags"]) == set(entry_data["tags"])

@pytest.mark.asyncio
async def test_get_entry(mock_journal_repository):
    # Ajouter une entrée
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entry to retrieve",
        "type_entree": "test"
    }
    
    added_entry = await mock_journal_repository.add_entry(entry_data)
    
    # Récupérer l'entrée
    result = await mock_journal_repository.get_entry(added_entry["id"])
    
    # Vérifier que l'entrée a été récupérée
    assert result is not None
    assert result["id"] == added_entry["id"]
    assert result["content"] == entry_data["texte"]

@pytest.mark.asyncio
async def test_update_entry(mock_journal_repository):
    # Ajouter une entrée
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entry to update",
        "type_entree": "test"
    }
    
    added_entry = await mock_journal_repository.add_entry(entry_data)
    
    # Mettre à jour l'entrée
    update_data = {
        "texte": "Updated entry",
        "type_entree": "updated"
    }
    
    updated_entry = await mock_journal_repository.update_entry(added_entry["id"], update_data)
    
    # Vérifier que l'entrée a été mise à jour
    assert updated_entry is not None
    assert updated_entry["id"] == added_entry["id"]
    assert updated_entry["content"] == update_data["texte"]
    assert updated_entry["type_entree"] == update_data["type_entree"]

@pytest.mark.asyncio
async def test_delete_entry(mock_journal_repository):
    # Ajouter une entrée
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entry to delete",
        "type_entree": "test"
    }
    
    added_entry = await mock_journal_repository.add_entry(entry_data)
    
    # Supprimer l'entrée
    result = await mock_journal_repository.delete_entry(added_entry["id"])
    
    # Vérifier que l'entrée a été supprimée
    assert result is True
    
    # Vérifier que l'entrée n'existe plus
    deleted_entry = await mock_journal_repository.get_entry(added_entry["id"])
    assert deleted_entry is None

@pytest.mark.asyncio
async def test_get_entries(mock_journal_repository):
    # Ajouter plusieurs entrées
    entries = [
        {
            "date": "2023-01-01",
            "texte": "Entry 1",
            "type_entree": "test"
        },
        {
            "date": "2023-01-02",
            "texte": "Entry 2",
            "type_entree": "test"
        },
        {
            "date": "2023-01-03",
            "texte": "Entry 3",
            "type_entree": "project"
        }
    ]
    
    for entry in entries:
        await mock_journal_repository.add_entry(entry)
    
    # Récupérer toutes les entrées
    all_entries = await mock_journal_repository.get_entries()
    assert len(all_entries) == 3
    
    # Récupérer les entrées filtrées par date
    filtered_entries = await mock_journal_repository.get_entries(start_date="2023-01-02")
    assert len(filtered_entries) == 2
    
    # Récupérer les entrées filtrées par type
    filtered_entries = await mock_journal_repository.get_entries(type_entree="project")
    assert len(filtered_entries) == 1
    assert filtered_entries[0]["type_entree"] == "project"