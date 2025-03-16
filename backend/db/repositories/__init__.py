# db/repositories/__init__.py
from db.repositories.journal_repository import JournalRepository
from db.repositories.memoire_repository import MemoireRepository

__all__ = [
    "JournalRepository",
    "MemoireRepository"
]