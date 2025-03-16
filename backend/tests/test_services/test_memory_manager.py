# tests/test_services/test_memory_manager.py
import pytest
from datetime import datetime

@pytest.mark.asyncio
async def test_add_journal_entry(mock_memory_manager):
    # Créer une entrée de test
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Test entry for memory manager",
        "type_entree": "test",
        "tags": ["test", "manager"]
    }
    
    # Appeler la méthode add_journal_entry
    result = await mock_memory_manager.add_journal_entry(entry_data)
    
    # Vérifier que l'entrée a été ajoutée
    assert result is not None
    assert "id" in result
    assert result["content"] == entry_data["texte"]
    assert result["type_entree"] == entry_data["type_entree"]
    assert set(result["tags"]) == set(entry_data["tags"])

@pytest.mark.asyncio
async def test_add_and_get_memoire_section(mock_memory_manager):
    # Créer une section de test
    section_data = {
        "titre": "Test Section",
        "contenu": "Test content for section",
        "ordre": 1,
        "parent_id": None
    }
    
    # Ajouter la section
    result = await mock_memory_manager.add_memoire_section(section_data)
    
    # Vérifier que la section a été ajoutée
    assert result is not None
    assert "id" in result
    assert result["titre"] == section_data["titre"]
    assert result["contenu"] == section_data["contenu"]
    
    # Récupérer la section
    section = await mock_memory_manager.get_memoire_section(result["id"])
    
    # Vérifier que la section récupérée est correcte
    assert section is not None
    assert section["id"] == result["id"]
    assert section["titre"] == section_data["titre"]
    assert section["contenu"] == section_data["contenu"]

@pytest.mark.asyncio
async def test_update_memoire_section(mock_memory_manager):
    # Créer une section de test
    section_data = {
        "titre": "Section to update",
        "contenu": "Original content",
        "ordre": 1,
        "parent_id": None
    }
    
    # Ajouter la section
    section = await mock_memory_manager.add_memoire_section(section_data)
    
    # Mettre à jour la section
    update_data = {
        "titre": "Updated Section",
        "contenu": "Updated content"
    }
    
    updated_section = await mock_memory_manager.update_memoire_section(section["id"], update_data)
    
    # Vérifier que la section a été mise à jour
    assert updated_section is not None
    assert updated_section["id"] == section["id"]
    assert updated_section["titre"] == update_data["titre"]
    assert updated_section["contenu"] == update_data["contenu"]
    assert updated_section["ordre"] == section["ordre"]  # Non modifié

@pytest.mark.asyncio
async def test_delete_memoire_section(mock_memory_manager):
    # Créer une section de test
    section_data = {
        "titre": "Section to delete",
        "contenu": "This will be deleted",
        "ordre": 1,
        "parent_id": None
    }
    
    # Ajouter la section
    section = await mock_memory_manager.add_memoire_section(section_data)
    
    # Supprimer la section
    result = await mock_memory_manager.delete_memoire_section(section["id"])
    
    # Vérifier que la section a été supprimée
    assert result is True
    
    # Vérifier que la section n'existe plus
    deleted_section = await mock_memory_manager.get_memoire_section(section["id"])
    assert deleted_section is None

@pytest.mark.asyncio
async def test_link_journal_to_section(mock_memory_manager):
    # Créer une entrée de journal
    entry_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "texte": "Entry to link",
        "type_entree": "test"
    }
    
    entry = await mock_memory_manager.add_journal_entry(entry_data)
    
    # Créer une section
    section_data = {
        "titre": "Section for link",
        "contenu": "This will link to an entry",
        "ordre": 1,
        "parent_id": None
    }
    
    section = await mock_memory_manager.add_memoire_section(section_data)
    
    # Lier l'entrée à la section
    result = await mock_memory_manager.link_entry_to_section(section["id"], entry["id"])
    
    # Vérifier que le lien a été créé
    assert result is True
    
    # Récupérer la section pour vérifier que l'entrée est liée
    updated_section = await mock_memory_manager.get_memoire_section(section["id"])
    
    # Vérifier que l'entrée est présente dans la liste des entrées liées
    assert updated_section is not None
    assert "journal_entries" in updated_section
    assert len(updated_section["journal_entries"]) > 0
    assert updated_section["journal_entries"][0]["id"] == entry["id"]