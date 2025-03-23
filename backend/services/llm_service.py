import os
import random
import logging
from typing import List, Optional, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

# Tentative d'importation de l'orchestrateur LLM existant
try:
    from llm_orchestrator import LLMOrchestrator
    llm_orchestrator = LLMOrchestrator(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    )
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    llm_orchestrator = None
    logger.warning("LLMOrchestrator non disponible, utilisation du mode fallback")

def get_llm_orchestrator():
    """
    Retourne l'instance de l'orchestrateur LLM.
    
    Returns:
        L'instance LLMOrchestrator ou None si non disponible
    """
    return llm_orchestrator

async def get_embeddings(text: str) -> List[float]:
    """
    Génère des embeddings pour un texte donné
    
    Args:
        text: Le texte à encoder
        
    Returns:
        Une liste de valeurs représentant l'embedding
    """
    if not text:
        # Embedding vide pour un texte vide
        return [0.0] * 384
    
    if ORCHESTRATOR_AVAILABLE and llm_orchestrator:
        try:
            # Utiliser l'orchestrateur pour obtenir des embeddings
            return await llm_orchestrator.get_embeddings(text)
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings avec l'orchestrateur: {str(e)}")
    
    # Fallback: Générer un embedding aléatoire
    logger.warning("Utilisation du fallback pour les embeddings (vecteur aléatoire)")
    return generate_random_embedding(text)

def generate_random_embedding(text: str = None, dimension: int = 384) -> List[float]:
    """
    Génère un embedding aléatoire
    
    Args:
        text: Texte pour la graine (optionnel)
        dimension: Dimension du vecteur d'embedding
        
    Returns:
        Une liste de valeurs représentant l'embedding
    """
    # Utiliser le texte comme graine si fourni
    if text:
        random.seed(hash(text) % (2**32))
    
    # Générer un vecteur aléatoire
    embedding = [random.uniform(-0.1, 0.1) for _ in range(dimension)]
    
    # Normaliser le vecteur (longueur = 1)
    magnitude = sum(x**2 for x in embedding) ** 0.5
    if magnitude > 0:
        embedding = [x / magnitude for x in embedding]
    
    return embedding

async def execute_ai_task(task_type: str, prompt: str, system_prompt: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Exécute une tâche d'IA via l'orchestrateur LLM
    
    Args:
        task_type: Type de tâche (generate, improve, etc.)
        prompt: Texte de la requête
        system_prompt: Prompt système (optionnel)
        context: Contexte supplémentaire (optionnel)
        
    Returns:
        Réponse générée
    """
    # Ajouter le contexte au prompt si fourni
    if context:
        context_str = "\n\nContexte:\n"
        if "sections" in context:
            context_str += "\nSections pertinentes:\n"
            for section in context.get("sections", [])[:3]:
                title = section.get("titre", "")
                preview = section.get("content_preview", "")[:200]
                context_str += f"- {title}: {preview}...\n"
        
        if "journal_entries" in context:
            context_str += "\nEntrées de journal pertinentes:\n"
            for entry in context.get("journal_entries", [])[:3]:
                date = entry.get("date", "")
                content = entry.get("content", "")[:200]
                context_str += f"- {date}: {content}...\n"
        
        prompt = prompt + context_str
    
    if ORCHESTRATOR_AVAILABLE and llm_orchestrator:
        try:
            # Utiliser l'orchestrateur pour exécuter la tâche
            return await llm_orchestrator.execute_task(task_type, prompt, system_prompt)
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche IA: {str(e)}")
            return f"Une erreur est survenue lors de l'exécution de la tâche: {str(e)}"
    else:
        # Message de fallback
        return f"Le service LLM n'est pas disponible actuellement. Votre requête était: {prompt[:100]}..."

async def generate_text_streaming(task_type: str, prompt: str, system_prompt: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
    """
    Génère du texte en streaming via l'orchestrateur LLM
    
    Args:
        task_type: Type de tâche (generate, improve, etc.)
        prompt: Texte de la requête
        system_prompt: Prompt système (optionnel)
        context: Contexte supplémentaire (optionnel)
        
    Yields:
        Chunks de texte générés
    """
    # Ajouter le contexte au prompt si fourni
    if context:
        context_str = "\n\nContexte:\n"
        if "sections" in context:
            context_str += "\nSections pertinentes:\n"
            for section in context.get("sections", [])[:3]:
                title = section.get("titre", "")
                preview = section.get("content_preview", "")[:200]
                context_str += f"- {title}: {preview}...\n"
        
        if "journal_entries" in context:
            context_str += "\nEntrées de journal pertinentes:\n"
            for entry in context.get("journal_entries", [])[:3]:
                date = entry.get("date", "")
                content = entry.get("content", "")[:200]
                context_str += f"- {date}: {content}...\n"
        
        prompt = prompt + context_str
    
    if ORCHESTRATOR_AVAILABLE and llm_orchestrator:
        try:
            # Utiliser l'orchestrateur pour exécuter la tâche en streaming
            async for chunk in llm_orchestrator.generate_text_streaming(prompt, system_prompt):
                yield chunk
        except Exception as e:
            logger.error(f"Erreur lors de la génération en streaming: {str(e)}")
            yield f"Une erreur est survenue lors de la génération en streaming: {str(e)}"
    else:
        # Simulation de streaming en fallback
        yield f"Le service LLM n'est pas disponible actuellement."
        await asyncio.sleep(0.5)
        yield f" Votre requête était: {prompt[:50]}..."