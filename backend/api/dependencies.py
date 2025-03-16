from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional

from core.config import settings

# En-tête d'authentification API (optionnel)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: Optional[str] = Depends(api_key_header)):
    """Vérifie que l'API key est valide si elle est configurée"""
    if settings.API_KEY:
        if not api_key or api_key != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key invalide ou manquante",
                headers={"WWW-Authenticate": "ApiKey"},
            )
    return True