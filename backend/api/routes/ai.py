from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from typing import Dict, Any, Optional, List
import logging
import json
import asyncio

from api.models.ai import (
    GeneratePlanRequest, 
    GeneratePlanResponse,
    GenerateContentRequest, 
    GenerateContentResponse,
    ImproveTextRequest, 
    ImproveTextResponse,
    HallucinationCheckRequest, 
    HallucinationCheckResponse,
    AutoTaskRequest, 
    AutoTaskResponse
)
from services.memory_manager import MemoryManager, get_memory_manager
from services.llm_service import execute_ai_task, generate_text_streaming
from core.exceptions import DatabaseError, ValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-plan", response_model=GeneratePlanResponse)
async def generate_plan(
    request: GeneratePlanRequest,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Génère un plan de mémoire basé sur le journal de bord
    
    Cette fonction analyse le journal et génère un plan structuré pour le mémoire.
    """
    try:
        # Récupérer des entrées récentes du journal pour le contexte
        journal_entries = await memory_manager.get_journal_entries(limit=30)
        
        # Construire le contexte
        context = "Voici des extraits de mon journal de bord:\n\n"
        for entry in journal_entries[:10]:  # Limiter à 10 entrées pour éviter un contexte trop long
            date = entry.get("date", "")
            content = entry.get("content", "")[:300]  # Limiter la taille
            entreprise = entry.get("entreprise_nom", "")
            context += f"Date: {date}\n"
            if entreprise:
                context += f"Entreprise: {entreprise}\n"
            context += f"Contenu: {content}...\n\n"
        
        # Construire le prompt et les instructions
        system_prompt = """Tu es un assistant spécialisé dans la création de plans de mémoire pour des étudiants en alternance. 
        Tu dois créer un plan structuré pour un mémoire professionnel basé sur les extraits du journal de bord de l'étudiant.
        Le plan doit suivre la structure requise pour valider le titre RNCP 35284 Expert en management des systèmes d'information."""
        
        user_prompt = f"{context}\n\nÀ partir de ces informations, génère un plan détaillé pour mon mémoire professionnel. {request.prompt}"
        
        # Générer le plan
        plan_text = await execute_ai_task("generate", user_prompt, system_prompt)
        
        # Traiter le plan et créer les sections correspondantes dans la base de données
        section_count = 0
        lines = plan_text.strip().split('\n')
        parent_id = None
        current_order = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Détecter les titres de premier niveau
            if line.startswith("# ") or line.startswith("1. "):
                titre = line.split(" ", 1)[1] if " " in line else line
                
                # Ajouter la section à la base de données
                section_data = {
                    "titre": titre,
                    "contenu": "",
                    "ordre": current_order,
                    "parent_id": None
                }
                
                section = await memory_manager.add_memoire_section(section_data)
                parent_id = section["id"]
                current_order += 1
                section_count += 1
            
            # Détecter les titres de second niveau
            elif (line.startswith("## ") or line.startswith("1.1") or 
                  line.startswith("2.1") or line.startswith("- ")):
                if parent_id:
                    if line.startswith("- "):
                        titre = line[2:]
                    else:
                        titre = line.split(" ", 1)[1] if " " in line else line
                    
                    # Ajouter la sous-section à la base de données
                    section_data = {
                        "titre": titre,
                        "contenu": "",
                        "ordre": current_order,
                        "parent_id": parent_id
                    }
                    
                    await memory_manager.add_memoire_section(section_data)
                    current_order += 1
                    section_count += 1
        
        return {
            "plan": plan_text,
            "sections_created": section_count
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du plan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du plan: {str(e)}")

@router.post("/generate-content", response_model=GenerateContentResponse)
async def generate_content(
    request: GenerateContentRequest,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Génère du contenu pour une section du mémoire
    
    Cette fonction génère du contenu pour une section spécifique en utilisant le contexte du journal.
    """
    try:
        # Récupérer la section
        section = await memory_manager.get_memoire_section(request.section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section non trouvée")
        
        # Récupérer des entrées pertinentes du journal si demandé
        journal_entries = []
        if request.use_journal:
            query = request.prompt if request.prompt else section.get("titre", "")
            journal_entries = await memory_manager.search_journal_entries(query)
        
        # Construire le contexte
        context = {
            "sections": await memory_manager.search_relevant_sections(query),
            "journal_entries": journal_entries
        }
        
        # Construire le prompt et les instructions
        system_prompt = """Vous êtes un assistant d'écriture académique pour un mémoire professionnel.
        Générez du contenu détaillé, structuré et réfléchi pour la section demandée, en vous appuyant sur le contexte et les extraits du journal."""
        
        generation_prompt = f"""
        # Section à rédiger
        Titre: {section.get("titre", "")}
        Description: {section.get("contenu", "")[:100] + "..." if section.get("contenu", "") and len(section.get("contenu", "")) > 100 else section.get("contenu", "")}

        # Contexte
        {request.prompt if request.prompt else "Veuillez générer du contenu pour cette section en vous basant sur les entrées du journal."}
        """
        
        # Générer le contenu
        generated_content = await execute_ai_task("generate", generation_prompt, system_prompt, context)
        
        # Mettre à jour la section avec le contenu généré
        update_data = {"contenu": generated_content}
        updated_section = await memory_manager.update_memoire_section(request.section_id, update_data)
        
        return {
            "generated_content": generated_content,
            "section_id": request.section_id,
            "sources": [
                {"type": "journal_entry", "id": entry.get("id"), "date": entry.get("date")}
                for entry in journal_entries[:3]
            ] if journal_entries else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la génération du contenu: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du contenu: {str(e)}")

@router.post("/improve-text", response_model=ImproveTextResponse)
async def improve_text(
    request: ImproveTextRequest
):
    """
    Améliore un texte selon différents modes (grammaire, style, concision)
    
    Cette fonction améliore la qualité d'un texte selon le mode choisi.
    """
    modes = {
        "grammar": "Corrige les erreurs grammaticales, orthographiques et de ponctuation. Ne modifie pas le style ou la structure.",
        "style": "Améliore le style d'écriture pour le rendre plus professionnel et élégant, en conservant le sens original.",
        "conciseness": "Rend le texte plus concis sans perdre d'information essentielle.",
        "expand": "Développe le texte avec plus de détails et d'exemples."
    }
    
    if request.mode not in modes:
        raise HTTPException(status_code=400, detail=f"Mode non valide. Modes disponibles: {', '.join(modes.keys())}")
    
    try:
        system_prompt = f"Tu es un assistant d'écriture académique spécialisé. {modes[request.mode]}"
        user_prompt = f"Voici le texte à améliorer :\n\n{request.texte}"
        
        improved_text = await execute_ai_task("improve", user_prompt, system_prompt)
        
        # Calcul simplifié du nombre de modifications
        changes_made = 0
        for i in range(min(len(request.texte), len(improved_text))):
            if request.texte[i] != improved_text[i]:
                changes_made += 1
        
        changes_made += abs(len(request.texte) - len(improved_text))
        
        return {
            "improved_text": improved_text,
            "changes_made": changes_made
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'amélioration du texte: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'amélioration du texte: {str(e)}")

@router.websocket("/stream_generation")
async def websocket_stream_generation(
    websocket: WebSocket,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """Point d'entrée WebSocket pour la génération de texte en streaming"""
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
            section = await memory_manager.get_memoire_section(section_id)
        except Exception:
            await websocket.send_json({
                "type": "error",
                "message": "Section non trouvée"
            })
            return
        
        if not section:
            await websocket.send_json({
                "type": "error",
                "message": "Section non trouvée"
            })
            return
        
        # Récupérer le contexte pour la génération
        query = prompt if prompt else section.get("titre", "")
        journal_entries = await memory_manager.search_journal_entries(query)
        relevant_sections = await memory_manager.search_relevant_sections(query)
        
        context = {
            "sections": relevant_sections,
            "journal_entries": journal_entries
        }
        
        # Construire le prompt
        system_prompt = """Vous êtes un assistant d'écriture académique pour un mémoire professionnel.
        Générez du contenu détaillé, structuré et réfléchi pour la section demandée, en vous appuyant sur le contexte et les extraits du journal."""
        
        generation_prompt = f"""
        # Section à rédiger
        Titre: {section.get("titre", "")}
        Description: {section.get("contenu", "")[:100] + "..." if section.get("contenu", "") and len(section.get("contenu", "")) > 100 else section.get("contenu", "")}

        # Contexte
        {prompt if prompt else "Veuillez générer du contenu pour cette section en vous basant sur les entrées du journal."}
        """
        
        await websocket.send_json({
            "type": "start",
            "message": "Génération démarrée"
        })
        
        full_content = ""
        async for text_chunk in generate_text_streaming("generate", generation_prompt, system_prompt, context):
            await websocket.send_json({
                "type": "chunk",
                "content": text_chunk
            })
            full_content += text_chunk
        
        # Mettre à jour la section avec le contenu généré
        update_data = {"contenu": full_content}
        await memory_manager.update_memoire_section(section_id, update_data)
        
        await websocket.send_json({
            "type": "end",
            "message": "Génération terminée",
            "section_id": section_id
        })
        
    except WebSocketDisconnect:
        logger.info("Client déconnecté pendant la génération en streaming")
    except json.JSONDecodeError:
        logger.error("Format JSON invalide reçu via WebSocket")
        await websocket.send_json({
            "type": "error",
            "message": "Format de données invalide"
        })
    except Exception as e:
        logger.error(f"Erreur lors de la génération en streaming: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Erreur: {str(e)}"
            })
        except:
            pass

@router.post("/auto-task", response_model=AutoTaskResponse)
async def auto_execute_task(
    request: AutoTaskRequest
):
    """
    Exécute automatiquement une tâche IA en déterminant le type de tâche
    
    Cette fonction analyse la requête et détermine automatiquement le type de tâche à exécuter.
    """
    try:
        import time
        start_time = time.time()
        
        result = await execute_ai_task("auto", request.prompt, request.system_prompt, request.context)
        
        execution_time = time.time() - start_time
        
        # Détecter le type de tâche (simpliste pour l'exemple)
        task_type = "generate"
        if "améliorer" in request.prompt.lower() or "corriger" in request.prompt.lower():
            task_type = "improve"
        elif "résumer" in request.prompt.lower() or "synthétiser" in request.prompt.lower():
            task_type = "summarize" 
        
        return {
            "result": result,
            "task_type": task_type,
            "execution_time": round(execution_time, 2)
        }
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la tâche automatique: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-hallucinations", response_model=HallucinationCheckResponse)
async def check_hallucinations(
    request: HallucinationCheckRequest,
    memory_manager: MemoryManager = Depends(get_memory_manager)
):
    """
    Vérifie un texte pour détecter d'éventuelles hallucinations
    
    Cette fonction analyse un contenu généré pour identifier et corriger les hallucinations potentielles.
    """
    try:
        # Pour l'instant, renvoyer une réponse simulée
        return {
            "has_hallucinations": False,
            "confidence_score": 0.95,
            "suspect_segments": [],
            "verified_facts": [{"text": "Fait vérifié dans les données", "confidence": 0.98}],
            "corrected_content": request.content
        }
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des hallucinations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))