from fastapi import APIRouter

from api.routes.journal import router as journal_router
from api.routes.memoire import router as memoire_router
from api.routes.ai import router as ai_router
from api.routes.search import router as search_router
from api.routes.export import router as export_router
from api.routes.admin import router as admin_router

# Ces variables sont importées par main.py
journal = journal_router
memoire = memoire_router
ai = ai_router
search = search_router
export = export_router
admin = admin_router