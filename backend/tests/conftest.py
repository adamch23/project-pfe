import pytest
from unittest.mock import AsyncMock, MagicMock
import sys
import os

# Ajout du chemin app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

# MOCK EARLY POUR EVITER LES TIMEOUTS LORS DE L'IMPORT
mock_client = MagicMock()
mock_database = MagicMock()

mock_collection = MagicMock()
mock_collection.find_one = AsyncMock(return_value=None)
mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="507f1f77bcf86cd799439011"))
mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))

mock_database.__getitem__.return_value = mock_collection
mock_database.command = AsyncMock(return_value={"ok": 1.0})

# Important: on modifie le module database AVANT que main.py ne soit chargé
import database
database.db = mock_database
database.client = mock_client

@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    """Mock global de la base de données Motor/MongoDB."""
    # Déjà mocké, on s'assure juste que monkeypatch l'applique pour les reloads éventuels
    monkeypatch.setattr(database, "db", mock_database)
    return mock_database
