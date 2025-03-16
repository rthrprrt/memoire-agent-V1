import asyncio
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Awaitable

logger = logging.getLogger(__name__)

class CircuitBreakerOpenError(Exception):
    """Exception levée quand un circuit est ouvert"""
    pass

class CircuitBreaker:
    """
    Implémentation du pattern Circuit Breaker pour protéger 
    contre les appels répétés à un service défaillant
    """
    
    CLOSED = "CLOSED"  # Circuit normal, les appels sont transmis
    OPEN = "OPEN"      # Circuit coupé, les appels sont bloqués
    HALF_OPEN = "HALF_OPEN"  # Mode test, quelques appels sont autorisés
    
    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: int = 60, 
                half_open_max_calls: int = 1):
        """
        Initialise un Circuit Breaker
        
        Args:
            name: Nom du circuit
            failure_threshold: Nombre d'échecs avant ouverture du circuit
            reset_timeout: Durée en secondes avant de tester à nouveau le circuit
            half_open_max_calls: Nombre maximum d'appels test en demi-ouverture
        """
        self.name = name
        self.state = self.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.half_open_max_calls = half_open_max_calls
        self.half_open_calls = 0
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker '{name}' initialisé avec seuil={failure_threshold}, timeout={reset_timeout}s")
    
    async def __aenter__(self):
        await self._before_call()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self._on_failure()
        else:
            await self._on_success()
        return False
    
    async def _before_call(self):
        """Vérifie l'état du circuit avant un appel"""
        async with self._lock:
            current_time = time.time()
            
            if self.state == self.OPEN:
                if current_time - self.last_failure_time > self.reset_timeout:
                    logger.info(f"Circuit '{self.name}' passe de OPEN à HALF_OPEN après {self.reset_timeout}s")
                    self.state = self.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit '{self.name}' ouvert, attendre {int(self.reset_timeout - (current_time - self.last_failure_time))}s"
                    )
            
            if self.state == self.HALF_OPEN and self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(
                    f"Circuit '{self.name}' en demi-ouverture, limite d'appels de test atteinte"
                )
            
            if self.state == self.HALF_OPEN:
                self.half_open_calls += 1
    
    async def _on_success(self):
        """Gère un appel réussi"""
        async with self._lock:
            if self.state == self.HALF_OPEN:
                logger.info(f"Circuit '{self.name}' passe de HALF_OPEN à CLOSED après un appel réussi")
                self.state = self.CLOSED
            self.failure_count = 0
    
    async def _on_failure(self):
        """Gère un appel échoué"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit '{self.name}' passe de CLOSED à OPEN après {self.failure_count} échecs"
                )
                self.state = self.OPEN
            
            if self.state == self.HALF_OPEN:
                logger.warning(f"Circuit '{self.name}' passe de HALF_OPEN à OPEN après un échec")
                self.state = self.OPEN
    
    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Exécute une fonction protégée par le circuit breaker
        
        Args:
            func: Fonction asynchrone à exécuter
            *args, **kwargs: Arguments à passer à la fonction
            
        Returns:
            Le résultat de la fonction
            
        Raises:
            CircuitBreakerOpenError: Si le circuit est ouvert
        """
        await self._before_call()
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retourne le statut actuel du circuit breaker
        
        Returns:
            Dict: Statut du circuit breaker
        """
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "reset_timeout": self.reset_timeout,
            "last_failure_time": datetime.fromtimestamp(self.last_failure_time) if self.last_failure_time > 0 else None,
            "half_open_calls": self.half_open_calls,
            "half_open_max_calls": self.half_open_max_calls
        }

# Circuit breakers globaux
generation_circuit = CircuitBreaker("ollama_generation")
embedding_circuit = CircuitBreaker("ollama_embedding")