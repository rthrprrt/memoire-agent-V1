"""
Routeur FastAPI pour les fonctionnalités d'IA du mémoire.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional, List
import logging
import json
import asyncio

from pydantic import BaseModel
from core.memory_manager import get_memory_manager
from services.llm_service import get_llm_orchestrator
from hallucination_detector import HallucinationDetector

# Configuration du logger
logger = logging.getLogger(__name__)

# Création du routeur
router = APIRouter()

class GeneratePlanRequest(BaseModel):
    """Modèle pour la génération d'un plan de mémoire."""
    prompt: str

class GenerateContentRequest(BaseModel):
    """Modèle pour la génération de contenu pour une section."""
    section_id: int
    prompt: Optional[str] = None
    check_hallucinations: bool = True
    
class ImproveTextRequest(BaseModel):
    """Modèle pour l'amélioration d'un texte."""
    texte: str
    mode: str = "grammar"  # grammar, style, conciseness, expand
    
class AutoTaskRequest(BaseModel):
    """Modèle pour l'exécution automatique d'une tâche."""
    prompt: str
    system_prompt: Optional[str] = None
    streaming: bool = False
    temperature: float = 0.7

@router.post("/generate-plan")
async def generate_plan(
    request: GeneratePlanRequest = Body(...),
    memory_manager = Depends(get_memory_manager),
    llm_orchestrator = Depends(get_llm_orchestrator)
):
    """
    Génère un plan structuré pour le mémoire en se basant sur les entrées du journal.
    """
    try:
        # Récupérer les entrées récentes du journal
        journal_entries = await memory_manager.get_journal_entries(limit=30)
        
        # Construire le contexte
        context = "Voici des extraits récents de mon journal de bord:\n\n"
        for entry in journal_entries:
            context += f"Date: {entry['date']}\n"
            if 'entreprise_nom' in entry:
                context += f"Entreprise: {entry['entreprise_nom']}\n"
            context += f"Type: {entry['type_entree']}\n"
            content_preview = entry.get('content', '')[:300] + "..." if len(entry.get('content', '')) > 300 else entry.get('content', '')
            context += f"Contenu: {content_preview}\n\n"
        
        # Construire le prompt système
        system_prompt = """Tu es un assistant spécialisé dans la création de plans de mémoire pour des étudiants en alternance. 
Tu dois créer un plan structuré pour un mémoire professionnel basé sur les extraits du journal de bord de l'étudiant.
Le plan doit suivre la structure requise pour valider le titre RNCP 35284 Expert en management des systèmes d'information."""
        
        # Construire le prompt utilisateur
        user_prompt = f"{context}\n\nÀ partir de ces informations, génère un plan détaillé pour mon mémoire professionnel. {request.prompt}"
        
        # Générer le plan
        plan_text = await llm_orchestrator.execute_task("generate", user_prompt, system_prompt)
        
        # Initialiser la structure dans la base de données
        await memory_manager.initialize_rncp_structure()
        
        return {"plan": plan_text}
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération du plan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du plan: {str(e)}")

@router.post("/generate-content")
async def generate_content(
    request: GenerateContentRequest = Body(...),
    memory_manager = Depends(get_memory_manager),
    llm_orchestrator = Depends(get_llm_orchestrator)
):
    """
    Génère du contenu pour une section du mémoire en utilisant le LLM.
    """
    try:
        # Récupérer la section
        section = await memory_manager.get_section(request.section_id)
        
        # Récupérer des entrées de journal pertinentes
        query = request.prompt if request.prompt else section["titre"] + " " + (section.get("content", "") or "")
        relevant_entries = await memory_manager.search_relevant_journal(query, limit=5)
        
        # Construire le prompt système
        system_prompt = """
        Vous êtes un assistant d'écriture académique pour un mémoire professionnel.
        Générez du contenu détaillé, structuré et réfléchi pour la section demandée,
        en vous appuyant sur les informations fournies.
        """
        
        # Construire le prompt utilisateur
        journal_content = ""
        for entry in relevant_entries:
            content_preview = entry.get("content", "")[:500] + "..." if len(entry.get("content", "")) > 500 else entry.get("content", "")
            journal_content += f"\n## Date: {entry['date']}\n{content_preview}\n"
        
        generation_prompt = f"""
        # Section à rédiger
        Titre: {section["titre"]}
        
        # Contexte
        {request.prompt if request.prompt else "Veuillez générer du contenu pour cette section en vous basant sur les entrées du journal."}
        
        # Entrées pertinentes du journal de bord
        {journal_content if journal_content else "Aucune entrée pertinente trouvée."}
        
        Rédigez un contenu détaillé, analytique et bien structuré pour cette section.
        """
        
        # Générer le contenu
        generated_content = await llm_orchestrator.execute_task("generate", generation_prompt, system_prompt)
        
        # Vérifier les hallucinations si demandé
        if request.check_hallucinations:
            detector = HallucinationDetector(memory_manager)
            context = {
                "sections": await memory_manager.search_relevant_sections(query),
                "journal_entries": relevant_entries
            }
            verification_results = await detector.check_content(generated_content, context)
            
            if verification_results["has_hallucinations"]:
                generated_content = verification_results["corrected_content"]
                verification_info = {
                    "hallucinations_detected": True,
                    "confidence_score": verification_results["confidence_score"],
                    "suspect_segments": len(verification_results["suspect_segments"]),
                    "corrected": True
                }
            else:
                verification_info = {
                    "hallucinations_detected": False,
                    "confidence_score": verification_results["confidence_score"]
                }
            
            # Mettre à jour le contenu de la section
            section["content"] = generated_content
            await memory_manager.save_section(section)
            
            return {
                "content": generated_content,
                "verification": verification_info,
                "section_id": request.section_id
            }
        else:
            # Mettre à jour le contenu de la section sans vérification
            section["content"] = generated_content
            await memory_manager.save_section(section)
            
            return {
                "content": generated_content,
                "section_id": request.section_id
            }
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération du contenu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du contenu: {str(e)}")

@router.post("/improve-text")
async def improve_text(
    request: ImproveTextRequest = Body(...),
    llm_orchestrator = Depends(get_llm_orchestrator)
):
    """
    Améliore un texte existant selon différents modes (grammaire, style, etc.).
    """
    try:
        # Définir les prompts système selon le mode
        system_prompts = {
            "grammar": "Tu es un correcteur orthographique et grammatical expert. Corrige les erreurs dans le texte fourni tout en préservant son sens et sa structure.",
            "style": "Tu es un expert en rédaction académique. Améliore le style d'écriture du texte fourni pour le rendre plus professionnel et adapté à un mémoire d'alternance.",
            "conciseness": "Tu es un expert en communication claire et concise. Réduis le texte fourni tout en préservant toutes les informations essentielles.",
            "expand": "Tu es un expert en rédaction. Développe et enrichis le texte fourni avec plus de détails et d'exemples pertinents."
        }
        
        # Vérifier le mode demandé
        mode = request.mode.lower()
        if mode not in system_prompts:
            raise HTTPException(status_code=400, detail=f"Mode non reconnu: {mode}")
        
        # Construire le prompt
        system_prompt = system_prompts[mode]
        user_prompt = f"Voici le texte à améliorer :\n\n{request.texte}"
        
        # Générer le texte amélioré
        improved_text = await llm_orchestrator.execute_task("improve", user_prompt, system_prompt)
        
        return {"improved_text": improved_text}
    
    except Exception as e:
        logger.error(f"Erreur lors de l'amélioration du texte: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'amélioration du texte: {str(e)}")

@router.post("/auto-task")
async def auto_execute_task(
    request: AutoTaskRequest = Body(...),
    llm_orchestrator = Depends(get_llm_orchestrator)
):
    """
    Exécute automatiquement une tâche en laissant l'orchestrateur LLM décider du modèle à utiliser.
    """
    try:
        # Exécuter la tâche
        result = await llm_orchestrator.execute_task("auto", request.prompt, request.system_prompt)
        
        return {"result": result}
    
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la tâche: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.post("/analyze-competences")
async def analyze_competences(
    memory_manager = Depends(get_memory_manager)
):
    """
    Analyse les compétences développées à partir des entrées du journal.
    """
    try:
        result = await memory_manager.analyze_competences_from_journal()
        return result
    
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse des compétences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")

@router.websocket("/ws/stream_generation")
async def websocket_stream_generation(
    websocket: WebSocket,
    memory_manager = Depends(get_memory_manager),
    llm_orchestrator = Depends(get_llm_orchestrator)
):
    """
    Point d'entrée WebSocket pour la génération de texte en streaming.
    """
    await websocket.accept()
    
    try:
        data = await websocket.receive_text()
        params = json.loads(data)
        
        section_id = params.get("section_id")
        prompt = params.get("prompt", "")
        
        if not section_id:
            await websocket.send_json({
                "type": "error",
                "message": "section_id est requis"
            })
            return
        
        try:
            section = await memory_manager.get_section(section_id)
        except ValueError:
            await websocket.send_json({
                "type": "error",
                "message": "Section non trouvée"
            })
            return
        
        query = prompt if prompt else section["titre"] + " " + (section.get("content", "") or "")
        relevant_entries = await memory_manager.search_relevant_journal(query)
        
        system_prompt = """
        Vous êtes un assistant d'écriture académique pour un mémoire professionnel.
        Générez du contenu détaillé, structuré et réfléchi pour la section demandée,
        en vous appuyant sur les informations fournies.
        """
        
        journal_content = ""
        for entry in relevant_entries[:3]:
            content_preview = entry.get("content", "")[:500] + "..." if len(entry.get("content", "")) > 500 else entry.get("content", "")
            journal_content += f"\n## Date: {entry['date']}\n{content_preview}\n"
        
        generation_prompt = f"""
        # Section à rédiger
        Titre: {section["titre"]}
        
        # Contexte
        {prompt if prompt else "Veuillez générer du contenu pour cette section en vous basant sur les entrées du journal."}
        
        # Entrées pertinentes du journal de bord
        {journal_content if journal_content else "Aucune entrée pertinente trouvée."}
        
        Rédigez un contenu détaillé, analytique et bien structuré pour cette section.
        """
        
        await websocket.send_json({
            "type": "start",
            "message": "Génération démarrée"
        })
        
        full_content = ""
        
        # Génération en streaming
        async for text_chunk in llm_orchestrator.generate_text_streaming("generate", generation_prompt, system_prompt):
            await websocket.send_json({
                "type": "chunk",
                "content": text_chunk
            })
            full_content += text_chunk
        
        # Mettre à jour la section avec le contenu complet
        section["content"] = full_content
        await memory_manager.save_section(section)
        
        # Vérifier les hallucinations en arrière-plan
        asyncio.create_task(verify_and_update_content(memory_manager, section, query, full_content))
        
        await websocket.send_json({
            "type": "end",
            "message": "Génération terminée",
            "section_id": section_id
        })
    
    except WebSocketDisconnect:
        logger.info("Client déconnecté pendant la génération en streaming")
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "message": "Format JSON invalide"
        })
    except Exception as e:
        logger.error(f"Erreur pendant la génération en streaming: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Erreur: {str(e)}"
            })
        except:
            pass

async def verify_and_update_content(memory_manager, section, query, content):
    """
    Vérifie le contenu généré pour détecter les hallucinations et met à jour la section si nécessaire.
    Exécuté en arrière-plan après une génération en streaming.
    """
    try:
        # Récupérer du contexte pour la vérification
        relevant_entries = await memory_manager.search_relevant_journal(query)
        relevant_sections = await memory_manager.search_relevant_sections(query)
        
        context = {
            "journal_entries": relevant_entries,
            "sections": relevant_sections
        }
        
        # Vérifier les hallucinations
        detector = HallucinationDetector(memory_manager)
        verification_results = await detector.check_content(content, context)
        
        # Si des hallucinations sont détectées, corriger et mettre à jour la section
        if verification_results["has_hallucinations"]:
            corrected_content = verification_results["corrected_content"]
            
            # Mettre à jour la section avec le contenu corrigé
            section["content"] = corrected_content
            await memory_manager.save_section(section)
            
            logger.info(f"Contenu de la section {section['id']} corrigé automatiquement après détection d'hallucinations")
    
    except Exception as e:
        logger.error(f"Erreur lors de la vérification en arrière-plan: {str(e)}")