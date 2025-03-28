import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import time
import tempfile
import logging
from pathlib import Path
import importlib.metadata
import traceback
try:
    import pkg_resources
except ImportError:
    pkg_resources = None

# Configuration du logging
try:
    from utils.logging_config import configure_streamlit_logging, get_logger
    logger = get_logger("app")
    configure_streamlit_logging()
except ImportError:
    # Fallback sur le logging standard si le module n'est pas disponible
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/frontend.log", mode="a")
        ]
    )
    logger = logging.getLogger("app")
    logger.info("Utilisation du logging standard (modules Rich et Loguru non disponibles)")

# Configuration de l'API
API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Configuration de Streamlit
st.set_page_config(
    page_title="Assistant Mémoire Alternance",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styles CSS personnalisés
st.markdown("""
<style>
    .main-title {
        text-align: center;
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    .section-title {
        font-size: 1.8rem;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    .subsection-title {
        font-size: 1.5rem;
        margin-top: 0.8rem;
        margin-bottom: 0.4rem;
    }
    .card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .tag {
        background-color: #6c757d;
        color: white;
        border-radius: 15px;
        padding: 2px 8px;
        margin-right: 5px;
        font-size: 0.8rem;
    }
    .entry-date {
        color: #6c757d;
        font-size: 0.9rem;
    }
    .progress-container {
        margin-bottom: 20px;
    }
    .entry-container {
        border-left: 3px solid #007bff;
        padding-left: 15px;
        margin-bottom: 20px;
    }
    .suspect-segment {
        background-color: #fff3cd;
        padding: 5px;
        border-radius: 3px;
        border-left: 3px solid #ffc107;
    }
    .verified-fact {
        background-color: #d4edda;
        padding: 5px;
        border-radius: 3px;
        border-left: 3px solid #28a745;
    }
    .hallucination-metrics {
        display: flex;
        justify-content: space-between;
        margin-bottom: 15px;
    }
    .hallucination-metric {
        text-align: center;
        padding: 10px;
        border-radius: 5px;
        background-color: #f8f9fa;
        width: 45%;
    }
</style>
""", unsafe_allow_html=True)

# --- Fonctions d'appel à l'API ---
def api_request(method, endpoint, **kwargs):
    """Fonction pour les requêtes API avec gestion d'erreurs robuste et logging amélioré"""
    max_retries = 3
    retry_delay = 1
    debug_mode = True  # Activer/désactiver le mode débogage
    
    if debug_mode:
        # Logger les détails de la requête en mode débogage
        params_str = f", params={kwargs.get('params', {})}" if 'params' in kwargs else ""
        data_str = f", data={kwargs.get('data', {})}" if 'data' in kwargs else ""
        json_str = f", json={kwargs.get('json', {})}" if 'json' in kwargs else ""
        logger.debug(f"Appel API {method.__name__.upper()} à {endpoint}{params_str}{data_str}{json_str}")
        st.info(f"DEBUG: Appel API {method.__name__.upper()} à {endpoint}")
    
    for retry in range(max_retries):
        try:
            url = f"{API_URL}/{endpoint}"
            if debug_mode:
                logger.debug(f"URL complète: {url}")
                st.info(f"DEBUG: URL complète: {url}")
            
            response = method(url, **kwargs, timeout=15)  # Augmentation du timeout
            
            if debug_mode:
                logger.debug(f"Statut de la réponse: {response.status_code}")
                st.info(f"DEBUG: Statut de la réponse: {response.status_code}")
                if response.status_code >= 400:
                    logger.warning(f"Corps de la réponse en erreur: {response.text}")
                    st.warning(f"DEBUG: Corps de la réponse en erreur: {response.text}")
            
            response.raise_for_status()
            
            # Tenter de parser la réponse JSON
            try:
                json_response = response.json()
                if debug_mode:
                    log_response = str(json_response)[:100] + "..." if len(str(json_response)) > 100 else str(json_response)
                    logger.debug(f"Réponse JSON reçue: {log_response}")
                    st.info(f"DEBUG: Réponse JSON reçue: {log_response}")
                return json_response
            except ValueError as json_err:
                if debug_mode:
                    logger.warning(f"Réponse reçue mais pas au format JSON: {response.text[:100]}...")
                    st.warning(f"DEBUG: Réponse reçue mais pas au format JSON: {response.text[:100]}...")
                logger.error(f"Erreur de décodage JSON: {str(json_err)}")
                st.error(f"Erreur de décodage JSON: {str(json_err)}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            if debug_mode:
                logger.warning(f"Erreur de connexion: {str(e)}")
                st.warning(f"DEBUG: Erreur de connexion: {str(e)}")
            
            if retry < max_retries - 1:
                logger.warning(f"Tentative de connexion {retry+1}/{max_retries} échouée. Nouvelle tentative dans {retry_delay} secondes...")
                st.warning(f"Tentative de connexion {retry+1}/{max_retries} échouée. Nouvelle tentative dans {retry_delay} secondes...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponentiel
            else:
                logger.error(f"Impossible de se connecter à l'API ({API_URL}) après {max_retries} tentatives.")
                st.error(f"Impossible de se connecter à l'API ({API_URL}) après {max_retries} tentatives.")
                # Essayer alternatives si on n'est pas déjà en train de tester une URL alternative
                if API_URL != "http://localhost:8000":
                    try:
                        logger.info("Tentative avec URL alternative: http://localhost:8000")
                        st.info("Tentative avec URL alternative: http://localhost:8000")
                        url = f"http://localhost:8000/{endpoint}"
                        response = method(url, **kwargs, timeout=15)
                        response.raise_for_status()
                        return response.json()
                    except Exception as alt_err:
                        if debug_mode:
                            logger.error(f"Erreur avec URL alternative: {str(alt_err)}")
                            st.error(f"DEBUG: Erreur avec URL alternative: {str(alt_err)}")
                return None
                
        except requests.exceptions.Timeout:
            if debug_mode:
                logger.warning("Timeout de la requête")
                st.warning(f"DEBUG: Timeout de la requête")
            
            if retry < max_retries - 1:
                logger.warning(f"Délai d'attente dépassé (tentative {retry+1}/{max_retries}). Nouvelle tentative dans {retry_delay} secondes...")
                st.warning(f"Délai d'attente dépassé (tentative {retry+1}/{max_retries}). Nouvelle tentative dans {retry_delay} secondes...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("Délai d'attente dépassé lors de la connexion à l'API.")
                st.error("Délai d'attente dépassé lors de la connexion à l'API.")
                return None
                
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_msg = f"Erreur HTTP {status_code}"
            
            if debug_mode:
                logger.warning(f"Erreur HTTP {status_code}")
                logger.debug(f"Entêtes de réponse: {dict(e.response.headers)}")
                logger.debug(f"Corps de réponse: {e.response.text}")
                st.warning(f"DEBUG: Erreur HTTP {status_code}")
                st.warning(f"DEBUG: Entêtes de réponse: {dict(e.response.headers)}")
                st.warning(f"DEBUG: Corps de réponse: {e.response.text}")
            
            try:
                error_detail = e.response.json().get("detail", "Pas de détails disponibles")
                error_msg += f": {error_detail}"
            except:
                if debug_mode:
                    logger.warning("Impossible de décoder la réponse d'erreur comme JSON")
                    st.warning(f"DEBUG: Impossible de décoder la réponse d'erreur comme JSON")
                error_msg += f". Corps de la réponse: {e.response.text[:100]}..."
            
            logger.error(error_msg)
            st.error(error_msg)
            
            # Pour les erreurs 404, tenter une autre solution si c'est un endpoint avec préfixe/sans préfixe
            if status_code == 404 and retry == 0:
                if endpoint.startswith("journal/"):
                    # Essayer sans le préfixe
                    new_endpoint = endpoint.replace("journal/", "")
                    logger.info(f"Tentative sans préfixe: {new_endpoint}")
                    st.info(f"Tentative sans préfixe: {new_endpoint}")
                    try:
                        return api_request(method, new_endpoint, **kwargs)
                    except:
                        pass
                elif not any(endpoint.startswith(prefix) for prefix in ["journal/", "memoire/", "ai/", "admin/", "search/", "export/"]):
                    # Essayer avec le préfixe journal
                    new_endpoint = f"journal/{endpoint}"
                    logger.info(f"Tentative avec préfixe journal: {new_endpoint}")
                    st.info(f"Tentative avec préfixe journal: {new_endpoint}")
                    try:
                        return api_request(method, new_endpoint, **kwargs)
                    except:
                        pass
            
            return None
            
        except Exception as e:
            if debug_mode:
                import traceback
                trace = traceback.format_exc()
                logger.error(f"Exception détaillée: {trace}")
                st.error(f"DEBUG: Exception détaillée: {trace}")
            
            logger.error(f"Erreur inattendue: {str(e)}")
            st.error(f"Erreur inattendue: {str(e)}")
            return None

# --- Fonctions pour la gestion des imports de documents ---
def get_import_sources():
    result = api_request(requests.get, "import/sources")
    if result is None:
        return []
    return result

def cleanup_all_imports():
    """Supprime toutes les entrées issues d'imports de documents"""
    result = api_request(requests.delete, "import/cleanup")
    return result is not None

def cleanup_document_import(filename):
    """Supprime les entrées issues d'un document spécifique"""
    result = api_request(requests.delete, f"import/document/{filename}")
    return result is not None

def cleanup_entries_by_date(start_date=None, end_date=None):
    """Supprime les entrées de journal dans une plage de dates"""
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    result = api_request(requests.delete, "journal/entries/cleanup/date", params=params)
    return result is not None

def cleanup_all_entries(confirm=False):
    """Supprime TOUTES les entrées de journal (dangereux)"""
    params = {"confirm": str(confirm).lower()}
    result = api_request(requests.delete, "journal/entries/cleanup/all", params=params)
    return result is not None

# --- Fonctions d'interrogation de l'API pour le journal ---
def get_entreprises():
    result = api_request(requests.get, "entreprises")
    if result is None:
        return [
            {"id": 1, "nom": "AI Builders", "date_debut": "2023-09-01", "date_fin": None},
            {"id": 2, "nom": "Gecina", "date_debut": "2023-09-01", "date_fin": None}
        ]
    return result

def get_tags():
    result = api_request(requests.get, "tags")
    if result is None:
        return []
    return result

def get_journal_entries(start_date=None, end_date=None, entreprise_id=None, type_entree=None, tag=None):
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if entreprise_id:
        params["entreprise_id"] = entreprise_id
    if type_entree:
        params["type_entree"] = type_entree
    if tag:
        params["tag"] = tag
    result = api_request(requests.get, "journal/entries", params=params)
    if result is None:
        return []
    return result

def add_journal_entry(entry_data):
    return api_request(requests.post, "journal/entries", json=entry_data)

def update_journal_entry(entry_id, entry_data):
    return api_request(requests.put, f"journal/entries/{entry_id}", json=entry_data)

def delete_journal_entry(entry_id):
    result = api_request(requests.delete, f"journal/entries/{entry_id}")
    return result is not None

def search_entries(query):
    result = api_request(requests.get, "search", params={"query": query})
    if result is None:
        return []
    return result

# --- Fonctions d'interrogation de l'API pour le mémoire ---
def get_memoire_sections(parent_id=None):
    params = {}
    if parent_id is not None:
        params["parent_id"] = parent_id
    result = api_request(requests.get, "memoire/sections", params=params)
    if result is None:
        return []
    return result

def get_memoire_section(section_id):
    return api_request(requests.get, f"memoire/sections/{section_id}")

def add_memoire_section(section_data):
    return api_request(requests.post, "memoire/sections", json=section_data)

def update_memoire_section(section_id, section_data):
    return api_request(requests.put, f"memoire/sections/{section_id}", json=section_data)

def delete_memoire_section(section_id):
    result = api_request(requests.delete, f"memoire/sections/{section_id}")
    return result is not None

def save_section_content(section_id, content):
    data = {"content": content}
    return api_request(requests.post, f"memoire/sections/{section_id}/save", json=data)

# --- Fonctions d'interrogation de l'API pour l'IA ---
def generate_plan(prompt):
    return api_request(requests.post, "ai/generate-plan", json={"prompt": prompt})

def generate_content(section_id, prompt=None):
    data = {"section_id": section_id}
    if prompt:
        data["prompt"] = prompt
    return api_request(requests.post, "ai/generate-content", json=data)

def improve_text(texte, mode):
    return api_request(requests.post, "ai/improve-text", json={"texte": texte, "mode": mode})

# --- Fonctions d'API pour la détection d'hallucinations ---
def verify_content(content, context=None):
    data = {"content": content}
    if context:
        data["context"] = context
    return api_request(requests.post, "ai/check-hallucinations", json=data)

def improve_hallucinated_content(content, context=None):
    data = {"content": content}
    if context:
        data["context"] = context
    return api_request(requests.post, "ai/improve-content", json=data)

# --- Fonctions pour le streaming et autres ---
def generate_content_streaming(section_id, prompt=None):
    data = {"section_id": section_id}
    if prompt:
        data["prompt"] = prompt
    try:
        url = f"{API_URL}/ai/stream_generation"
        import websocket
        import json
        
        ws = websocket.create_connection(f"ws://{API_URL.replace('http://', '')}/ai/stream_generation")
        ws.send(json.dumps(data))
        
        content_placeholder = st.empty()
        content_text = ""
        
        while True:
            try:
                message = ws.recv()
                data = json.loads(message)
                
                if data["type"] == "chunk":
                    content_text += data["content"]
                    content_placeholder.text_area("Contenu généré en streaming", content_text, height=300)
                elif data["type"] == "end":
                    break
                elif data["type"] == "error":
                    st.error(data["message"])
                    break
            except websocket.WebSocketConnectionClosedException:
                break
            except Exception as e:
                st.error(f"Erreur lors du streaming: {str(e)}")
                break
        
        ws.close()
        return content_text
    except Exception as e:
        st.error(f"Erreur lors de la génération en streaming: {str(e)}")
        return None

def get_references():
    result = api_request(requests.get, "bibliography")
    if result is None:
        return []
    return result

def add_reference(ref_data):
    return api_request(requests.post, "bibliography", json=ref_data)

def export_memory(format="pdf"):
    try:
        response = requests.post(f"{API_URL}/export/{format}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'exportation: {str(e)}")
        return None

def analyze_document(uploaded_file):
    try:
        mime_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), mime_type)}
        
        # Essayer d'abord l'URL directe
        url = f"{API_URL}/import/document/analyze"
        st.info(f"Tentative d'analyse à: {url}")
        
        try:
            response = requests.post(url, files=files)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # Si ça échoue, essayer avec le préfixe /journal
            st.warning("URL directe a échoué, tentative avec l'URL préfixée...")
            url = f"{API_URL}/journal/import/document/analyze"
            st.info(f"Nouvelle tentative d'analyse à: {url}")
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), mime_type)}  # Recréer files car le stream a été consommé
            response = requests.post(url, files=files)
            response.raise_for_status()
        
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'analyse du document: {str(e)}")
        return None

def import_document(uploaded_file, entreprise_id=None):
    try:
        mime_type = "application/pdf" if uploaded_file.name.lower().endswith('.pdf') else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), mime_type)}
        data = {}
        if entreprise_id:
            data["entreprise_id"] = str(entreprise_id)
        
        # Essayer d'abord l'URL directe
        url = f"{API_URL}/import/document"
        st.info(f"Tentative d'envoi à: {url}")
        
        try:
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            # Si ça échoue, essayer avec le préfixe /journal
            st.warning("URL directe a échoué, tentative avec l'URL préfixée...")
            url = f"{API_URL}/journal/import/document"
            st.info(f"Nouvelle tentative d'envoi à: {url}")
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), mime_type)}  # Recréer files car le stream a été consommé
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
        
        # Log d'information sur la réponse
        st.success(f"Code de statut: {response.status_code}")
        return response.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"Erreur HTTP lors de l'import du document: {str(e)}")
        # Afficher plus de détails sur l'erreur
        if hasattr(e, 'response') and e.response is not None:
            st.error(f"Détails: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Erreur lors de l'import du document: {str(e)}")
        return None

# Maintenir les fonctions originales pour la compatibilité
def analyze_pdf(uploaded_file):
    return analyze_document(uploaded_file)

def import_pdf(uploaded_file, entreprise_id=None):
    return import_document(uploaded_file, entreprise_id)

def get_embedding_cache_status():
    return api_request(requests.get, "admin/cache")

def clear_embedding_cache():
    return api_request(requests.post, "admin/cache/clear")

def get_circuit_breaker_status():
    return api_request(requests.get, "admin/health")

def create_backup(description=None):
    data = {}
    if description:
        data["description"] = description
    return api_request(requests.post, "admin/backup/create", json=data)

def restore_backup(backup_id):
    return api_request(requests.post, f"admin/backup/{backup_id}/restore", json={"confirm": True})

def get_all_api_routes():
    return api_request(requests.get, "admin/routes")

def get_route_details(path):
    return api_request(requests.get, f"admin/routes/{path}")

def get_database_structure():
    """
    Récupère la structure de la base de données (tables, colonnes, etc.)
    
    Returns:
        Dict avec les informations sur la structure de la base de données ou None en cas d'erreur
    """
    return api_request(requests.get, "admin/database/structure")

def execute_sql_query(query, params=None):
    """
    Exécute une requête SQL en lecture seule pour le débogage
    
    Args:
        query: Requête SQL à exécuter (SELECT uniquement)
        params: Paramètres à utiliser dans la requête (optionnel)
        
    Returns:
        Dict avec les résultats de la requête ou None en cas d'erreur
    """
    payload = {
        "query": query
    }
    if params:
        payload["params"] = params
        
    return api_request(requests.post, "admin/database/query", json=payload)

def test_api_route(route_path, method="GET", params=None, json_data=None, headers=None):
    """
    Teste une route API avec des paramètres personnalisés et en mode verbose
    
    Args:
        route_path: Chemin de la route à tester
        method: Méthode HTTP (GET, POST, PUT, DELETE)
        params: Paramètres de requête (dictionnaire)
        json_data: Données JSON pour le corps de la requête (pour POST/PUT)
        headers: En-têtes HTTP personnalisés
        
    Returns:
        Dict avec la réponse et les détails de la requête/réponse
    """
    method_func = getattr(requests, method.lower())
    
    # Construire le dictionnaire de données pour l'appel
    request_args = {}
    if params:
        request_args["params"] = params
    if json_data:
        request_args["json"] = json_data
    if headers:
        request_args["headers"] = headers
    
    # Ajouter des en-têtes de debug
    if not headers:
        request_args["headers"] = {}
    request_args["headers"]["X-Debug"] = "true"
    
    try:
        # Effectuer la requête avec capture du temps de réponse
        import time
        start_time = time.time()
        response = method_func(f"{API_URL}/{route_path}", **request_args, timeout=15)
        request_time = time.time() - start_time
        
        # Capturer les détails de la réponse
        response_details = {
            "status_code": response.status_code,
            "status_text": response.reason,
            "headers": dict(response.headers),
            "elapsed_ms": round(request_time * 1000, 2),
            "content_type": response.headers.get("Content-Type", ""),
            "content_length": len(response.content),
        }
        
        # Tenter de parser la réponse selon le type de contenu
        if "application/json" in response.headers.get("Content-Type", ""):
            try:
                response_data = response.json()
            except ValueError:
                response_data = {"error": "Contenu JSON invalide", "raw": response.text[:1000]}
        else:
            response_data = {"raw": response.text[:1000]}
        
        return {
            "success": True,
            "response": response_data,
            "details": response_details,
            "request": {
                "method": method,
                "url": f"{API_URL}/{route_path}",
                "params": params,
                "json": json_data,
                "headers": request_args["headers"]
            }
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "request": {
                "method": method,
                "url": f"{API_URL}/{route_path}",
                "params": params,
                "json": json_data,
                "headers": request_args.get("headers", {})
            }
        }

# --- Interface utilisateur ---
with st.sidebar:
    st.title("Assistant Mémoire")
    st.subheader("Navigation")
    page = st.radio("", ["Tableau de bord", "Journal de bord", "Éditeur de mémoire", "Chat assistant", "Import de documents", "Admin & Outils", "Diagnostic"])

# --- Pages ---
if page == "Tableau de bord":
    st.markdown("<h1 class='main-title'>Tableau de bord</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    entries = get_journal_entries()
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Entrées de journal")
        st.metric("Total", len(entries))
        st.markdown("</div>", unsafe_allow_html=True)
    sections = get_memoire_sections()
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Sections du mémoire")
        st.metric("Total", len(sections))
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Avancement global")
        sections_with_content = sum(1 for s in sections if s.get("content"))
        progress = sections_with_content / max(len(sections), 1) * 100
        st.progress(progress / 100)
        st.metric("Pourcentage", f"{progress:.1f}%")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<h2 class='section-title'>Entrées récentes</h2>", unsafe_allow_html=True)
    recent_entries = entries[:5]
    if recent_entries:
        for entry in recent_entries:
            st.markdown("<div class='entry-container'>", unsafe_allow_html=True)
            st.markdown(f"<p class='entry-date'>{entry['date']}</p>", unsafe_allow_html=True)
            tags_html = "".join(f"<span class='tag'>{tag}</span>" for tag in entry.get("tags", []))
            st.markdown(tags_html, unsafe_allow_html=True)
            text_preview = entry.get("content", "")[:200] + "..." if len(entry.get("content", "")) > 200 else entry.get("content", "")
            st.write(text_preview)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Aucune entrée récente trouvée.")
    st.markdown("<h2 class='section-title'>Tags populaires</h2>", unsafe_allow_html=True)
    tags = get_tags()
    if tags:
        df_tags = pd.DataFrame({
            "Tag": [tag["nom"] for tag in tags],
            "Nombre d'entrées": [tag["count"] for tag in tags]
        })
        st.bar_chart(df_tags.set_index("Tag"))
    else:
        st.info("Aucun tag trouvé.")

elif page == "Journal de bord":
    st.markdown("<h1 class='main-title'>Journal de bord</h1>", unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["Ajouter une entrée", "Consulter les entrées", "Recherche"])
    with tab1:
        st.markdown("<h2 class='section-title'>Nouvelle entrée</h2>", unsafe_allow_html=True)
        entreprises = get_entreprises()
        entreprise_options = {e["nom"]: e["id"] for e in entreprises}
        with st.form("journal_entry_form"):
            date = st.date_input("Date", datetime.now())
            default_entreprise = None
            for e in entreprises:
                start_date = datetime.strptime(e["date_debut"], "%Y-%m-%d").date()
                end_date = datetime.strptime(e["date_fin"], "%Y-%m-%d").date() if e["date_fin"] else None
                if start_date <= date and (end_date is None or date <= end_date):
                    default_entreprise = e["nom"]
                    break
            entreprise_index = list(entreprise_options.keys()).index(default_entreprise) if default_entreprise in entreprise_options else 0
            entreprise = st.selectbox("Entreprise", list(entreprise_options.keys()), index=entreprise_index)
            type_entree = st.selectbox("Type d'entrée", ["quotidien", "projet", "formation", "réflexion"])
            texte = st.text_area("Contenu", height=300)
            all_tags = get_tags()
            existing_tags = [tag["nom"] for tag in all_tags]
            use_existing_tags = st.checkbox("Utiliser des tags existants")
            if use_existing_tags and existing_tags:
                selected_tags = st.multiselect("Tags", existing_tags)
            else:
                tags_input = st.text_input("Tags (séparés par des virgules)")
                selected_tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
            submitted = st.form_submit_button("Enregistrer")
            if submitted:
                if not texte:
                    st.error("Le contenu ne peut pas être vide.")
                else:
                    entry_data = {
                        "date": date.strftime("%Y-%m-%d"),
                        "texte": texte,
                        "entreprise_id": entreprise_options[entreprise],
                        "type_entree": type_entree,
                        "tags": selected_tags if selected_tags and selected_tags[0] else None
                    }
                    result = add_journal_entry(entry_data)
                    if result:
                        st.success("Entrée ajoutée avec succès.")
    
    with tab2:
        st.markdown("<h2 class='section-title'>Consulter les entrées</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Date de début", datetime.now() - timedelta(days=30))
            entreprises = get_entreprises()
            entreprise_options = {e["nom"]: e["id"] for e in entreprises}
            entreprise = st.selectbox("Entreprise (filtre)", ["Toutes"] + list(entreprise_options.keys()))
        with col2:
            end_date = st.date_input("Date de fin", datetime.now())
            all_tags = get_tags()
            tag_options = [tag["nom"] for tag in all_tags]
            tag = st.selectbox("Tag (filtre)", ["Tous"] + tag_options)
        
        entreprise_id = entreprise_options[entreprise] if entreprise != "Toutes" else None
        tag_filter = tag if tag != "Tous" else None
        
        if st.button("Rechercher"):
            entries = get_journal_entries(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                entreprise_id=entreprise_id,
                tag=tag_filter
            )
            
            if entries:
                for entry in entries:
                    st.markdown(f"<div class='entry-container'>", unsafe_allow_html=True)
                    st.markdown(f"<p class='entry-date'>{entry['date']}</p>", unsafe_allow_html=True)
                    tags_html = "".join(f"<span class='tag'>{tag}</span>" for tag in entry.get("tags", []))
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.write(entry.get("content", ""))
                    
                    col1, col2, col3 = st.columns([1, 1, 3])
                    entry_id = entry['id']
                    with col1:
                        if st.button(f"Modifier #{entry_id}", key=f"edit_{entry_id}"):
                            st.session_state[f'edit_entry_{entry_id}'] = entry
                    with col2:
                        if st.button(f"Supprimer #{entry_id}", key=f"delete_{entry_id}"):
                            if delete_journal_entry(entry_id):
                                st.success(f"Entrée {entry_id} supprimée")
                    
                    # Afficher le formulaire d'édition si l'entrée est sélectionnée pour modification
                    if f'edit_entry_{entry_id}' in st.session_state:
                        with st.form(f"edit_entry_form_{entry_id}"):
                            edit_texte = st.text_area(f"Modifier contenu #{entry_id}", entry.get("content", ""), height=200)
                            edit_tags = st.text_input(f"Modifier tags #{entry_id}", ", ".join(entry.get("tags", [])))
                            if st.form_submit_button("Enregistrer modifications"):
                                update_data = {
                                    "texte": edit_texte,
                                    "tags": [tag.strip() for tag in edit_tags.split(",")]
                                }
                                if update_journal_entry(entry_id, update_data):
                                    st.success(f"Entrée {entry_id} mise à jour")
                                    del st.session_state[f'edit_entry_{entry_id}']
                    
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Aucune entrée trouvée avec ces critères.")
    
    with tab3:
        st.markdown("<h2 class='section-title'>Recherche</h2>", unsafe_allow_html=True)
        search_query = st.text_input("Rechercher dans le journal")
        if search_query:
            results = search_entries(search_query)
            if results:
                st.write(f"{len(results)} résultats trouvés.")
                for result in results:
                    st.markdown(f"<div class='entry-container'>", unsafe_allow_html=True)
                    st.markdown(f"<p class='entry-date'>{result['date']}</p>", unsafe_allow_html=True)
                    
                    # Afficher le score de similarité s'il est présent
                    if 'similarity' in result:
                        st.markdown(f"<span style='background-color: #e6f7ff; padding: 3px 8px; border-radius: 10px;'>Score: {result['similarity']:.2f}</span>", unsafe_allow_html=True)
                    
                    tags_html = "".join(f"<span class='tag'>{tag}</span>" for tag in result.get("tags", []))
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.write(result.get("content", ""))
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Aucun résultat trouvé.")

elif page == "Éditeur de mémoire":
    st.markdown("<h1 class='main-title'>Éditeur de mémoire</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["Plan", "Édition des sections", "Vérification d'hallucinations", "Bibliographie"])
    
    with tab1:
        st.markdown("<h2 class='section-title'>Plan du mémoire</h2>", unsafe_allow_html=True)
        
        plan_col1, plan_col2 = st.columns(2)
        with plan_col1:
            if st.button("Générer un plan"):
                with plan_col2:
                    prompt = st.text_area("Instructions pour la génération du plan (optionnel)", height=100)
                    if st.button("Confirmer génération"):
                        with st.spinner("Génération du plan en cours..."):
                            result = generate_plan(prompt)
                            if result:
                                st.success("Plan généré avec succès!")
                                st.write(result.get("plan", ""))
        
        st.markdown("<h3 class='subsection-title'>Plan actuel</h3>", unsafe_allow_html=True)
        root_sections = get_memoire_sections()
        
        if root_sections:
            for section in root_sections:
                st.markdown(f"**{section['titre']}**")
                sub_sections = get_memoire_sections(section['id'])
                for sub in sub_sections:
                    st.markdown(f"- {sub['titre']}")
        else:
            st.info("Aucune section trouvée. Générez un plan ou ajoutez des sections manuellement.")
        
        with st.expander("Ajouter une section manuellement"):
            with st.form("add_section_form"):
                section_title = st.text_input("Titre de la section")
                parent_sections = [("Aucun (section racine)", None)] + [(s['titre'], s['id']) for s in root_sections]
                parent_option = st.selectbox("Section parente", range(len(parent_sections)), format_func=lambda x: parent_sections[x][0])
                parent_id = parent_sections[parent_option][1]
                section_order = st.number_input("Ordre", min_value=0, value=0)
                section_content = st.text_area("Contenu initial (optionnel)", height=100)
                
                if st.form_submit_button("Ajouter la section"):
                    if section_title:
                        section_data = {
                            "titre": section_title,
                            "content": section_content,
                            "ordre": section_order,
                            "parent_id": parent_id
                        }
                        result = add_memoire_section(section_data)
                        if result:
                            st.success("Section ajoutée avec succès!")
    
    with tab2:
        st.markdown("<h2 class='section-title'>Édition des sections</h2>", unsafe_allow_html=True)
        
        # Liste des sections disponibles
        all_sections = []
        root_sections = get_memoire_sections()
        
        for section in root_sections:
            all_sections.append((f"{section['titre']}", section['id']))
            sub_sections = get_memoire_sections(section['id'])
            for sub in sub_sections:
                all_sections.append((f"--- {sub['titre']}", sub['id']))
        
        if all_sections:
            selected_section_index = st.selectbox("Sélectionner une section à éditer", 
                                                  range(len(all_sections)), 
                                                  format_func=lambda x: all_sections[x][0])
            section_id = all_sections[selected_section_index][1]
            section = get_memoire_section(section_id)
            
            if section:
                with st.form("edit_section_form"):
                    edit_title = st.text_input("Titre", section['titre'])
                    edit_content = st.text_area("Contenu", section.get('content', ''), height=400)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Enregistrer les modifications"):
                            update_data = {
                                "titre": edit_title,
                                "content": edit_content
                            }
                            result = update_memoire_section(section_id, update_data)
                            if result:
                                st.success("Section mise à jour avec succès!")
                    
                    with col2:
                        generate_content_button = st.form_submit_button("Générer du contenu avec l'IA")
                
                if generate_content_button:
                    prompt = st.text_area("Instructions spécifiques pour l'IA (optionnel)", height=100)
                    if st.button("Confirmer génération"):
                        with st.spinner("Génération du contenu en cours..."):
                            result = generate_content(section_id, prompt)
                            if result:
                                st.success("Contenu généré avec succès!")
                                generated_content = result.get('content', '')
                                st.text_area("Contenu généré", generated_content, height=400)
                                if st.button("Utiliser ce contenu"):
                                    update_data = {"content": generated_content}
                                    update_result = update_memoire_section(section_id, update_data)
                                    if update_result:
                                        st.success("Section mise à jour avec le contenu généré!")
                
                # Afficher les entrées de journal associées
                if 'journal_entries' in section and section['journal_entries']:
                    st.markdown("<h3 class='subsection-title'>Entrées de journal associées</h3>", unsafe_allow_html=True)
                    for entry in section['journal_entries']:
                        st.markdown(f"<div class='entry-container'>", unsafe_allow_html=True)
                        st.markdown(f"<p class='entry-date'>{entry.get('date', '')}</p>", unsafe_allow_html=True)
                        content = entry.get("content", "")
                        preview = content[:200] + "..." if len(content) > 200 else content
                        st.write(preview)
                        st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Aucune section disponible. Générez un plan ou ajoutez des sections manuellement.")
    
    with tab3:
        st.markdown("<h2 class='section-title'>Vérification d'hallucinations</h2>", unsafe_allow_html=True)
        st.write("Cet outil détecte et corrige les affirmations potentiellement inexactes ou non vérifiables dans votre mémoire.")
        
        # Choix entre le texte saisi ou une section existante
        source_option = st.radio("Source du contenu à vérifier", ["Saisir un texte", "Sélectionner une section existante"])
        
        if source_option == "Saisir un texte":
            content_to_verify = st.text_area("Contenu à vérifier", height=200, 
                                           placeholder="Saisissez ici le texte à vérifier pour détecter d'éventuelles hallucinations...")
        else:
            all_sections = []
            root_sections = get_memoire_sections()
            
            for section in root_sections:
                all_sections.append((f"{section['titre']}", section['id']))
                sub_sections = get_memoire_sections(section['id'])
                for sub in sub_sections:
                    all_sections.append((f"--- {sub['titre']}", sub['id']))
            
            if all_sections:
                selected_section_index = st.selectbox("Sélectionner une section à vérifier", 
                                                    range(len(all_sections)), 
                                                    format_func=lambda x: all_sections[x][0],
                                                    key="verify_section_select")
                if len(all_sections) > 0:
                    section_id = all_sections[selected_section_index][1]
                    section = get_memoire_section(section_id)
                    if section and section.get('content'):
                        content_to_verify = section.get('content', '')
                        st.text_area("Contenu de la section", content_to_verify, height=200)
                    else:
                        st.warning("Cette section ne contient pas de contenu à vérifier.")
                        content_to_verify = ""
            else:
                st.info("Aucune section disponible.")
                content_to_verify = ""
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Vérifier le contenu"):
                if content_to_verify:
                    with st.spinner("Analyse en cours..."):
                        result = verify_content(content_to_verify)
                        if result:
                            # Afficher les résultats de la vérification
                            st.markdown("<div class='hallucination-metrics'>", unsafe_allow_html=True)
                            st.markdown(f"<div class='hallucination-metric'>Score de confiance: {result['confidence_score']:.2f}</div>", unsafe_allow_html=True)
                            if result["has_hallucinations"]:
                                st.markdown(f"<div class='hallucination-metric' style='color: #dc3545;'>Hallucinations détectées: Oui</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='hallucination-metric' style='color: #28a745;'>Hallucinations détectées: Non</div>", unsafe_allow_html=True)
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            if result["has_hallucinations"]:
                                st.error("Des hallucinations potentielles ont été détectées!")
                                st.markdown("<h4>Segments suspects:</h4>", unsafe_allow_html=True)
                                for i, segment in enumerate(result["suspect_segments"]):
                                    st.markdown(f"<div class='suspect-segment'>Segment {i+1}: {segment['text']}</div>", unsafe_allow_html=True)
                            else:
                                st.success("Aucune hallucination détectée!")
                            
                            if result["verified_facts"]:
                                st.markdown("<h4>Faits vérifiés:</h4>", unsafe_allow_html=True)
                                for i, fact in enumerate(result["verified_facts"]):
                                    st.markdown(f"<div class='verified-fact'>{fact['text']}</div>", unsafe_allow_html=True)
                else:
                    st.error("Veuillez entrer du contenu à vérifier.")

        with col2:
            if st.button("Améliorer automatiquement"):
                if content_to_verify:
                    with st.spinner("Amélioration en cours..."):
                        result = improve_hallucinated_content(content_to_verify)
                        if result and "corrected_content" in result:
                            st.success(f"Contenu amélioré avec {result.get('changes_made', 0)} modifications.")
                            improved_content = result["corrected_content"]
                            st.text_area("Contenu amélioré", improved_content, height=300)
                            
                            # Option pour mettre à jour la section directement
                            if source_option == "Sélectionner une section existante" and st.button("Remplacer le contenu de la section par la version améliorée"):
                                section_id = all_sections[selected_section_index][1]
                                update_data = {"content": improved_content}
                                update_result = update_memoire_section(section_id, update_data)
                                if update_result:
                                    st.success("Section mise à jour avec le contenu amélioré!")
                            
                            # Option pour voir les différences
                            if result.get("improvement_notes"):
                                st.markdown("<h4>Modifications apportées:</h4>", unsafe_allow_html=True)
                                for note in result["improvement_notes"]:
                                    st.markdown(f"- {note}")
                else:
                    st.error("Veuillez entrer du contenu à améliorer.")
    
    with tab4:
        st.markdown("<h2 class='section-title'>Bibliographie</h2>", unsafe_allow_html=True)
        references = get_references()
        
        if references:
            st.write(f"{len(references)} références bibliographiques")
            for ref in references:
                st.markdown(f"<div class='card'>", unsafe_allow_html=True)
                st.markdown(f"**{ref['title']}**")
                st.markdown(f"*{ref['citation']}*")
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Aucune référence bibliographique trouvée.")
        
        with st.expander("Ajouter une référence"):
            with st.form("add_reference_form"):
                ref_type = st.selectbox("Type", ["livre", "article", "site web", "rapport"])
                ref_title = st.text_input("Titre")
                ref_authors = st.text_input("Auteurs (séparés par des virgules)")
                ref_year = st.number_input("Année", min_value=1900, max_value=datetime.now().year, step=1)
                ref_publisher = st.text_input("Éditeur/Journal")
                
                if st.form_submit_button("Ajouter la référence"):
                    if ref_title and ref_authors:
                        authors_list = [a.strip() for a in ref_authors.split(",")]
                        ref_data = {
                            "type": ref_type,
                            "title": ref_title,
                            "authors": authors_list,
                            "year": ref_year,
                            "publisher": ref_publisher
                        }
                        result = add_reference(ref_data)
                        if result:
                            st.success("Référence ajoutée avec succès!")

elif page == "Chat assistant":
    st.markdown("<h1 class='main-title'>Chat Assistant</h1>", unsafe_allow_html=True)
    
    # Option pour vérifier les hallucinations dans les réponses générées
    col1, col2 = st.columns(2)
    with col1:
        streaming = st.checkbox("Utiliser le streaming des réponses longues")
    with col2:
        check_hallucinations = st.checkbox("Vérifier automatiquement les hallucinations", value=True)
    
    section_input = st.text_input("ID de la section (optionnel)")
    section_id = section_input if section_input else None
    prompt = st.text_area("Votre prompt", "Entrez votre demande ici...", height=150)
    
    if st.button("Générer du contenu"):
        if streaming:
            st.info("Génération en streaming...")
            generated = generate_content_streaming(section_id, prompt)
            st.text_area("Contenu généré", generated, height=300)
            
            # Vérification après génération si l'option est activée
            if check_hallucinations and generated:
                with st.spinner("Vérification des hallucinations..."):
                    verification = verify_content(generated)
                    if verification and verification.get("has_hallucinations"):
                        st.warning("Des hallucinations potentielles ont été détectées dans le contenu généré.")
                        st.markdown("<h4>Segments suspects:</h4>", unsafe_allow_html=True)
                        for segment in verification["suspect_segments"]:
                            st.markdown(f"<div class='suspect-segment'>{segment['text']}</div>", unsafe_allow_html=True)
                        
                        if st.button("Améliorer automatiquement le contenu"):
                            with st.spinner("Amélioration en cours..."):
                                improved = improve_hallucinated_content(generated)
                                if improved and "corrected_content" in improved:
                                    st.text_area("Contenu amélioré", improved["corrected_content"], height=300)
                    elif verification:
                        st.success("Aucune hallucination détectée dans le contenu généré.")
        else:
            with st.spinner("Génération en cours..."):
                generated_result = generate_content(section_id, prompt)
                if generated_result and "content" in generated_result:
                    generated = generated_result["content"]
                    st.text_area("Contenu généré", generated, height=300)
                    
                    # Vérification après génération si l'option est activée
                    if check_hallucinations:
                        with st.spinner("Vérification des hallucinations..."):
                            verification = verify_content(generated)
                            if verification and verification.get("has_hallucinations"):
                                st.warning("Des hallucinations potentielles ont été détectées dans le contenu généré.")
                                st.markdown("<h4>Segments suspects:</h4>", unsafe_allow_html=True)
                                for segment in verification["suspect_segments"]:
                                    st.markdown(f"<div class='suspect-segment'>{segment['text']}</div>", unsafe_allow_html=True)
                                
                                if st.button("Améliorer automatiquement le contenu"):
                                    with st.spinner("Amélioration en cours..."):
                                        improved = improve_hallucinated_content(generated)
                                        if improved and "corrected_content" in improved:
                                            st.text_area("Contenu amélioré", improved["corrected_content"], height=300)
                            elif verification:
                                st.success("Aucune hallucination détectée dans le contenu généré.")

elif page == "Import de documents":
    st.markdown("<h1 class='main-title'>Import de documents</h1>", unsafe_allow_html=True)
    
    # Onglets pour séparer les fonctionnalités
    import_tab, manage_tab = st.tabs(["Importer un document", "Gérer les imports"])
    
    with import_tab:
        st.write("Importez des fichiers PDF ou DOCX pour extraire automatiquement des entrées de journal.")
        
        uploaded_file = st.file_uploader("Choisissez un fichier PDF ou DOCX", type=["pdf", "docx"])
        if uploaded_file is not None:
            st.write(f"Fichier chargé: {uploaded_file.name}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Analyser le document"):
                    with st.spinner("Analyse en cours..."):
                        analysis = analyze_document(uploaded_file)
                        if analysis:
                            st.success(f"Analyse terminée. {len(analysis)} entrées potentielles trouvées.")
                            st.json(analysis)
            
            with col2:
                entreprises = get_entreprises()
                entreprise_options = {e["nom"]: e["id"] for e in entreprises}
                entreprise = st.selectbox("Entreprise pour l'import", list(entreprise_options.keys()))
                
                if st.button("Importer le document"):
                    with st.spinner("Import en cours..."):
                        result = import_document(uploaded_file, entreprise_id=entreprise_options[entreprise])
                        if result:
                            st.success(f"Document importé. {len(result.get('entries', []))} entrées créées.")
                            
                            # Option pour vérifier les hallucinations dans le contenu importé
                            if st.checkbox("Vérifier les hallucinations dans le contenu importé"):
                                for i, entry in enumerate(result.get('entries', [])):
                                    st.write(f"Vérification de l'entrée {i+1}...")
                                    verification = verify_content(entry.get('texte', ''))
                                    if verification and verification.get("has_hallucinations"):
                                        st.warning(f"Hallucinations détectées dans l'entrée {i+1}")
                                        for segment in verification["suspect_segments"]:
                                            st.markdown(f"<div class='suspect-segment'>{segment['text']}</div>", unsafe_allow_html=True)
    
    with manage_tab:
        st.write("Gérez les documents importés et nettoyez les entrées de journal associées.")
        
        # Récupérer les sources d'import
        with st.spinner("Chargement des imports..."):
            import_sources = get_import_sources()
        
        if not import_sources:
            st.info("Aucun document n'a été importé.")
        else:
            st.success(f"{len(import_sources)} documents importés trouvés.")
            
            # Afficher les imports dans un tableau
            sources_df = pd.DataFrame(import_sources)
            
            # Formater les données pour l'affichage
            if 'total_text_size' in sources_df.columns:
                sources_df['total_text_size'] = sources_df['total_text_size'].apply(
                    lambda x: f"{x/1024:.1f} KB" if x else "0 KB"
                )
            
            # Renommer les colonnes pour l'affichage
            column_rename = {
                'source_document': 'Nom du fichier',
                'entry_count': 'Nombre d\'entrées',
                'first_date': 'Première entrée',
                'last_date': 'Dernière entrée',
                'total_text_size': 'Taille de texte'
            }
            sources_df.rename(columns=column_rename, inplace=True)
            
            # Afficher le tableau
            st.dataframe(sources_df)
            
            # Option pour nettoyer un document spécifique
            st.subheader("Nettoyer un import spécifique")
            selected_doc = st.selectbox(
                "Sélectionnez un document à nettoyer",
                [doc['source_document'] for doc in import_sources]
            )
            
            if st.button("Nettoyer l'import sélectionné", key="clean_specific"):
                if selected_doc:
                    with st.spinner(f"Nettoyage de l'import '{selected_doc}'..."):
                        if cleanup_document_import(selected_doc):
                            st.success(f"Import '{selected_doc}' nettoyé avec succès.")
                            st.experimental_rerun()  # Actualiser la page
                        else:
                            st.error(f"Erreur lors du nettoyage de l'import '{selected_doc}'.")
            
            # Option pour tout nettoyer
            st.subheader("Nettoyer tous les imports")
            st.warning("⚠️ Cette action supprimera toutes les entrées de journal importées de documents.")
            
            confirm = st.checkbox("Je comprends que cette action est irréversible")
            if confirm:
                if st.button("Nettoyer tous les imports", key="clean_all"):
                    with st.spinner("Nettoyage de tous les imports..."):
                        if cleanup_all_imports():
                            st.success("Tous les imports ont été nettoyés avec succès.")
                            st.experimental_rerun()  # Actualiser la page
                        else:
                            st.error("Erreur lors du nettoyage des imports.")

elif page == "Admin & Outils":
    st.markdown("<h1 class='main-title'>Administration et Outils</h1>", unsafe_allow_html=True)
    
    # Cache des embeddings
    st.subheader("Cache des embeddings")
    cache_status = get_embedding_cache_status()
    if cache_status:
        st.write("Statut du cache :", cache_status)
    if st.button("Vider le cache des embeddings"):
        result = clear_embedding_cache()
        if result:
            st.success("Cache vidé avec succès.")
    st.markdown("---")
    
    # Statut du Circuit Breaker
    st.subheader("Statut du Circuit Breaker")
    circuit_status = get_circuit_breaker_status()
    if circuit_status:
        st.write("Circuit Breaker :", circuit_status)
    st.markdown("---")
    
    # Export du mémoire
    st.subheader("Export du Mémoire")
    export_format = st.selectbox("Format d'export", ["pdf", "docx"])
    if st.button("Exporter"):
        with st.spinner("Exportation en cours..."):
            export_result = export_memory(export_format)
            if export_result:
                st.success(f"Export réussi")
                st.json(export_result)
                
                if "download_url" in export_result:
                    download_url = export_result["download_url"]
                    full_url = f"{API_URL}/{download_url}"
                    st.markdown(f"[Télécharger le mémoire]({full_url})")
    st.markdown("---")
    
    # Gestion des entrées de journal
    st.subheader("Gestion des entrées de journal")
    
    # Créer des onglets pour organiser les différentes fonctionnalités de nettoyage
    cleanup_tabs = st.tabs(["Imports de documents", "Par date", "Toutes les entrées"])
    
    with cleanup_tabs[0]:
        # Gestion des imports de documents
        st.subheader("Imports de documents")
        if st.button("Voir les imports de documents", key="admin_view_imports"):
            with st.spinner("Chargement des imports..."):
                import_sources = get_import_sources()
                
                if not import_sources:
                    st.info("Aucun document n'a été importé.")
                else:
                    st.success(f"{len(import_sources)} documents importés trouvés.")
                    
                    # Afficher les imports dans un tableau
                    sources_df = pd.DataFrame(import_sources)
                    
                    # Formater les données pour l'affichage
                    if 'total_text_size' in sources_df.columns:
                        sources_df['total_text_size'] = sources_df['total_text_size'].apply(
                            lambda x: f"{x/1024:.1f} KB" if x else "0 KB"
                        )
                    
                    # Renommer les colonnes pour l'affichage
                    column_rename = {
                        'source_document': 'Nom du fichier',
                        'entry_count': 'Nombre d\'entrées',
                        'first_date': 'Première entrée',
                        'last_date': 'Dernière entrée',
                        'total_text_size': 'Taille de texte'
                    }
                    sources_df.rename(columns=column_rename, inplace=True)
                    
                    # Afficher le tableau
                    st.dataframe(sources_df)
                    
                    # Option pour supprimer un import spécifique
                    if len(import_sources) > 0:
                        source_names = [source['source_document'] for source in import_sources]
                        selected_doc = st.selectbox("Sélectionner un document à nettoyer", source_names)
                        
                        if st.button("Nettoyer le document sélectionné", key="admin_clean_selected"):
                            with st.spinner(f"Nettoyage des entrées du document '{selected_doc}'..."):
                                if cleanup_document_import(selected_doc):
                                    st.success(f"Les entrées du document '{selected_doc}' ont été nettoyées avec succès.")
                                    st.experimental_rerun()  # Rafraîchir pour mettre à jour la liste
                                else:
                                    st.error(f"Erreur lors du nettoyage des entrées du document '{selected_doc}'.")
                    
                    # Bouton pour accéder à la page de gestion complète
                    if st.button("Gérer les imports", key="goto_imports_page"):
                        st.session_state.page = "Import de documents"
                        st.experimental_rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Nettoyer tous les imports", key="admin_clean_all"):
                if st.checkbox("Confirmer la suppression de tous les imports", key="admin_confirm_clean"):
                    with st.spinner("Nettoyage de tous les imports..."):
                        if cleanup_all_imports():
                            st.success("Tous les imports ont été nettoyés avec succès.")
                            st.experimental_rerun()  # Actualiser la page
                        else:
                            st.error("Erreur lors du nettoyage des imports.")
                else:
                    st.warning("Veuillez confirmer cette action.")
    
    with cleanup_tabs[1]:
        # Suppression par date
        st.subheader("Suppression par date")
        
        st.info("Cette fonctionnalité permet de supprimer des entrées de journal dans une plage de dates spécifique.")
        
        # Options pour sélectionner la plage de dates
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "Date de début",
                None,
                help="Sélectionnez la date de début (incluse). Laissez vide pour ne pas spécifier de date minimale."
            )
        with date_col2:
            end_date = st.date_input(
                "Date de fin",
                None,
                help="Sélectionnez la date de fin (incluse). Laissez vide pour ne pas spécifier de date maximale."
            )
        
        # Convertir les dates au format YYYY-MM-DD si elles sont spécifiées
        start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
        end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None
        
        # Statut sur les filtres actifs
        filters_active = []
        if start_date_str:
            filters_active.append(f"À partir du {start_date_str}")
        if end_date_str:
            filters_active.append(f"Jusqu'au {end_date_str}")
            
        if filters_active:
            st.write("Filtres actifs: " + ", ".join(filters_active))
        
        # Option pour prévisualiser les entrées qui seront supprimées
        if start_date_str or end_date_str:
            if st.button("Prévisualiser les entrées", key="preview_date_entries"):
                preview_entries = get_journal_entries(start_date=start_date_str, end_date=end_date_str)
                st.write(f"{len(preview_entries)} entrées correspondant à ces critères.")
                if preview_entries:
                    preview_df = pd.DataFrame([
                        {
                            "ID": entry.get("id"),
                            "Date": entry.get("date"),
                            "Type": entry.get("type_entree"),
                            "Entreprise": entry.get("entreprise_nom"),
                            "Contenu": entry.get("content", "")[:50] + "..." if len(entry.get("content", "")) > 50 else entry.get("content", "")
                        }
                        for entry in preview_entries
                    ])
                    st.dataframe(preview_df)
            
            # Bouton de suppression
            if start_date_str or end_date_str:  # Au moins une date doit être spécifiée
                if st.button("Supprimer les entrées dans cette plage de dates", key="delete_date_entries"):
                    if st.checkbox("Je confirme vouloir supprimer ces entrées", key="confirm_date_delete"):
                        with st.spinner("Suppression des entrées..."):
                            if cleanup_entries_by_date(start_date_str, end_date_str):
                                st.success("Les entrées ont été supprimées avec succès.")
                            else:
                                st.error("Une erreur s'est produite lors de la suppression des entrées.")
                    else:
                        st.warning("Veuillez confirmer cette action dangereuse.")
            else:
                st.warning("Veuillez spécifier au moins une date (début ou fin).")
        else:
            st.warning("Veuillez spécifier au moins une date (début ou fin) pour continuer.")
    
    with cleanup_tabs[2]:
        # Suppression de toutes les entrées
        st.subheader("Suppression de toutes les entrées")
        
        st.warning("""⚠️ ATTENTION: Cette option va supprimer TOUTES les entrées de journal, 
                   y compris celles qui n'ont pas été créées via des imports de documents. 
                   Cette action est irréversible!""")
        
        # Demander une confirmation explicite
        st.info("Pour effectuer cette action, vous devez confirmer en écrivant 'SUPPRIMER TOUT' dans le champ ci-dessous.")
        
        confirmation_text = st.text_input("Confirmation", key="confirm_delete_all_text")
        
        if confirmation_text == "SUPPRIMER TOUT":
            if st.button("Supprimer toutes les entrées", key="delete_all_entries"):
                with st.spinner("Suppression de toutes les entrées..."):
                    if cleanup_all_entries(confirm=True):
                        st.success("Toutes les entrées ont été supprimées avec succès.")
                    else:
                        st.error("Une erreur s'est produite lors de la suppression des entrées.")
    st.markdown("---")
    
    # Sauvegarde et restauration
    st.subheader("Sauvegarde et Restauration")
    backup_col1, backup_col2 = st.columns(2)
    
    with backup_col1:
        description = st.text_input("Description de la sauvegarde", "Sauvegarde manuelle")
        if st.button("Créer une sauvegarde"):
            with st.spinner("Création de la sauvegarde..."):
                backup_result = create_backup(description)
                if backup_result:
                    st.success("Sauvegarde créée avec succès.")
                    st.json(backup_result)
    
    with backup_col2:
        backup_id = st.text_input("ID de la sauvegarde à restaurer")
        if st.button("Restaurer la sauvegarde"):
            if not backup_id:
                st.error("Veuillez entrer un ID de sauvegarde valide.")
            else:
                with st.spinner("Restauration en cours..."):
                    restore_result = restore_backup(backup_id)
                    if restore_result:
                        st.success("Sauvegarde restaurée avec succès.")
                        st.json(restore_result)

elif page == "Diagnostic":
    st.markdown("<h1 class='main-title'>Diagnostic et Débogage</h1>", unsafe_allow_html=True)
    
    # Informations sur l'environnement
    st.subheader("Informations d'environnement")
    st.info(f"URL de l'API: {API_URL}")
    
    # Test de connectivité
    st.subheader("Test de connectivité API")
    if st.button("Tester la connexion API"):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                st.success(f"Connexion réussie à {API_URL}/health (Code: {response.status_code})")
                st.json(response.json())
            else:
                st.error(f"Échec de la connexion: Code HTTP {response.status_code}")
                st.text(response.text)
        except Exception as e:
            st.error(f"Erreur de connexion: {str(e)}")
    
    # Explorateur d'API avancé
    st.subheader("Explorateur d'API avancé")
    
    # Créer trois onglets pour une organisation claire
    routes_tab, details_tab, test_tab = st.tabs(["Liste des routes", "Détails des routes", "Test avancé"])
    
    with routes_tab:
        st.write("Cet outil affiche toutes les routes API disponibles dans l'application.")
        
        # Récupérer la liste des routes du backend
        if "api_routes" not in st.session_state:
            with st.spinner("Chargement des routes API..."):
                routes = get_all_api_routes()
                if routes:
                    st.session_state.api_routes = routes
                    st.success(f"{len(routes)} routes trouvées")
                else:
                    st.error("Impossible de récupérer les routes API")
                    st.session_state.api_routes = []
        
        # Filtres pour les routes
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            # Filtre par méthode HTTP
            http_methods = set()
            for route in st.session_state.get("api_routes", []):
                http_methods.update(route.get("methods", []))
            
            selected_methods = st.multiselect(
                "Filtrer par méthode HTTP",
                sorted(list(http_methods)) if http_methods else ["GET", "POST", "PUT", "DELETE"],
                default=[]
            )
        
        with filter_col2:
            # Filtre par tag
            all_tags = set()
            for route in st.session_state.get("api_routes", []):
                all_tags.update(route.get("tags", []))
            
            selected_tags = st.multiselect(
                "Filtrer par tag",
                sorted(list(all_tags)),
                default=[]
            )
        
        # Recherche par texte
        search_term = st.text_input("Rechercher une route", placeholder="Exemple: journal, entries, etc.")
        
        # Appliquer les filtres
        filtered_routes = []
        for route in st.session_state.get("api_routes", []):
            # Filtrer par méthode HTTP
            if selected_methods and not any(method in selected_methods for method in route.get("methods", [])):
                continue
            
            # Filtrer par tag
            if selected_tags and not any(tag in selected_tags for tag in route.get("tags", [])):
                continue
            
            # Filtrer par texte de recherche
            if search_term and search_term.lower() not in route.get("path", "").lower() and search_term.lower() not in route.get("name", "").lower():
                continue
            
            filtered_routes.append(route)
        
        # Afficher les routes filtrées
        if filtered_routes:
            # Créer un tableau interactif
            routes_table = []
            for route in filtered_routes:
                methods = ", ".join(route.get("methods", []))
                tags = ", ".join(route.get("tags", []))
                
                # Ajouter une ligne au tableau
                routes_table.append({
                    "Path": route.get("path", ""),
                    "Méthodes": methods,
                    "Tags": tags,
                    "Nom": route.get("name", "")
                })
            
            # Convertir en dataframe pour l'affichage
            routes_df = pd.DataFrame(routes_table)
            st.dataframe(routes_df, use_container_width=True)
            
            # Bouton pour copier le tableau
            if st.button("Copier la liste des routes"):
                st.code(routes_df.to_csv(index=False), language="csv")
        else:
            st.warning("Aucune route ne correspond aux critères de filtrage.")
    
    with details_tab:
        st.write("Consultez les détails d'une route API spécifique, y compris sa documentation et ses paramètres.")
        
        # Option pour entrer manuellement le chemin ou le sélectionner
        input_method = st.radio("Sélection de la route", ["Choisir dans la liste", "Entrer manuellement"])
        
        if input_method == "Choisir dans la liste":
            # Créer un dictionnaire des routes pour le selectbox
            route_options = {}
            for route in st.session_state.get("api_routes", []):
                path = route.get("path", "")
                methods = ", ".join(route.get("methods", []))
                route_options[f"{methods} {path}"] = path
            
            selected_option = st.selectbox("Sélectionnez une route", list(route_options.keys()))
            selected_path = route_options.get(selected_option, "")
        else:
            selected_path = st.text_input("Entrez le chemin de la route", placeholder="Exemple: /journal/entries")
        
        if selected_path:
            # Nettoyer le chemin (retirer le / initial si présent)
            if selected_path.startswith("/"):
                selected_path = selected_path[1:]
            
            # Récupérer les détails de la route
            with st.spinner(f"Récupération des détails pour {selected_path}..."):
                route_details = get_route_details(selected_path)
                
                if route_details:
                    # Afficher les détails de base
                    st.subheader(f"Route: {route_details.get('path', '')}")
                    st.markdown(f"**Méthodes:** {', '.join(route_details.get('methods', []))}")
                    st.markdown(f"**Nom:** {route_details.get('name', 'Non spécifié')}")
                    st.markdown(f"**Tags:** {', '.join(route_details.get('tags', []))}")
                    
                    # Documentation
                    if route_details.get("description"):
                        st.markdown("### Documentation")
                        st.markdown(route_details.get("description", ""))
                    
                    # Paramètres
                    if route_details.get("parameters"):
                        st.markdown("### Paramètres")
                        params_data = []
                        for param in route_details.get("parameters", []):
                            params_data.append({
                                "Nom": param.get("name", ""),
                                "Type": param.get("type", ""),
                                "Défaut": param.get("default", ""),
                                "Genre": param.get("kind", "")
                            })
                        
                        # Afficher en tableau
                        st.table(pd.DataFrame(params_data))
                    
                    # Modèle de réponse
                    if route_details.get("response_model"):
                        st.markdown("### Modèle de réponse")
                        st.markdown(f"**Type:** {route_details.get('response_model', '')}")
                        
                        if route_details.get("response_schema"):
                            with st.expander("Schéma de réponse détaillé"):
                                st.json(route_details.get("response_schema"))
                    
                    # Bouton pour tester directement cette route
                    if st.button("Tester cette route"):
                        st.session_state.test_route_path = selected_path
                        st.session_state.test_route_method = route_details.get("methods", ["GET"])[0]
                        st.info("Veuillez passer à l'onglet 'Test avancé' pour tester cette route.")
                else:
                    st.error(f"Impossible de récupérer les détails pour la route {selected_path}")
    
    with test_tab:
        st.write("Testez n'importe quelle route API avec des paramètres personnalisés et examinez les détails complets de la réponse.")
        
        # Définir les variables de session pour la route à tester
        if "test_route_path" not in st.session_state:
            st.session_state.test_route_path = ""
        if "test_route_method" not in st.session_state:
            st.session_state.test_route_method = "GET"
        
        # Interface pour configurer le test
        test_col1, test_col2 = st.columns(2)
        
        with test_col1:
            route_path = st.text_input(
                "Chemin de la route", 
                value=st.session_state.test_route_path,
                placeholder="Exemple: journal/entries"
            )
        
        with test_col2:
            http_method = st.selectbox(
                "Méthode HTTP",
                ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"],
                index=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"].index(st.session_state.test_route_method)
                      if st.session_state.test_route_method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"] else 0
            )
        
        # Configuration avancée
        with st.expander("Paramètres de requête (optionnels)"):
            col1, col2 = st.columns(2)
            
            # Paramètres de requête (URL)
            with col1:
                st.subheader("Paramètres d'URL")
                
                # Interface pour ajouter des paramètres
                params = {}
                
                # Champs dynamiques pour les paramètres
                if "query_params" not in st.session_state:
                    st.session_state.query_params = [{"key": "", "value": ""}]
                
                for i, param in enumerate(st.session_state.query_params):
                    param_container = st.container()
                    with param_container:
                        p_col1, p_col2, p_col3 = st.columns([3, 3, 1])
                        with p_col1:
                            key = st.text_input(f"Nom {i+1}", value=param["key"], key=f"param_key_{i}")
                        with p_col2:
                            value = st.text_input(f"Valeur {i+1}", value=param["value"], key=f"param_value_{i}")
                        with p_col3:
                            if st.button("×", key=f"remove_param_{i}"):
                                st.session_state.query_params.pop(i)
                                st.experimental_rerun()
                        
                        # Mettre à jour les valeurs dans la session
                        if i < len(st.session_state.query_params):
                            st.session_state.query_params[i]["key"] = key
                            st.session_state.query_params[i]["value"] = value
                        
                        # Ajouter au dictionnaire de paramètres
                        if key:
                            params[key] = value
                
                if st.button("+ Ajouter un paramètre"):
                    st.session_state.query_params.append({"key": "", "value": ""})
                    st.experimental_rerun()
            
            # Corps de la requête JSON (pour POST/PUT)
            with col2:
                st.subheader("Corps de la requête (JSON)")
                json_body = st.text_area(
                    "Données JSON",
                    value="{\n  \n}",
                    height=200,
                    help="Saisissez un objet JSON valide pour le corps de la requête POST/PUT"
                )
                
                # Valider le JSON
                json_data = None
                if json_body and json_body.strip():
                    try:
                        json_data = json.loads(json_body)
                        st.success("JSON valide ✅")
                    except json.JSONDecodeError as e:
                        st.error(f"JSON invalide: {str(e)}")
        
        # En-têtes HTTP
        with st.expander("En-têtes HTTP personnalisés"):
            headers = {}
            
            # Champs dynamiques pour les en-têtes
            if "http_headers" not in st.session_state:
                st.session_state.http_headers = [{"key": "", "value": ""}]
            
            for i, header in enumerate(st.session_state.http_headers):
                header_container = st.container()
                with header_container:
                    h_col1, h_col2, h_col3 = st.columns([3, 3, 1])
                    with h_col1:
                        key = st.text_input(f"En-tête {i+1}", value=header["key"], key=f"header_key_{i}")
                    with h_col2:
                        value = st.text_input(f"Valeur de l'en-tête {i+1}", value=header["value"], key=f"header_value_{i}")
                    with h_col3:
                        if st.button("×", key=f"remove_header_{i}"):
                            st.session_state.http_headers.pop(i)
                            st.experimental_rerun()
                    
                    # Mettre à jour les valeurs dans la session
                    if i < len(st.session_state.http_headers):
                        st.session_state.http_headers[i]["key"] = key
                        st.session_state.http_headers[i]["value"] = value
                    
                    # Ajouter au dictionnaire d'en-têtes
                    if key:
                        headers[key] = value
            
            if st.button("+ Ajouter un en-tête"):
                st.session_state.http_headers.append({"key": "", "value": ""})
                st.experimental_rerun()
            
            # Option pour mode verbeux
            verbose_mode = st.checkbox("Mode verbeux (afficher tous les détails de la requête/réponse)", value=True)
        
        # Bouton pour exécuter le test
        if st.button("Exécuter le test", key="execute_test"):
            if not route_path:
                st.error("Veuillez spécifier un chemin de route.")
            else:
                with st.spinner(f"Test de la route {route_path} en cours..."):
                    # Nettoyer le chemin (retirer le / initial si présent)
                    if route_path.startswith("/"):
                        route_path = route_path[1:]
                    
                    # Stocker le chemin et la méthode pour utilisation future
                    st.session_state.test_route_path = route_path
                    st.session_state.test_route_method = http_method
                    
                    # Exécuter le test
                    result = test_api_route(
                        route_path=route_path,
                        method=http_method,
                        params=params if params else None,
                        json_data=json_data if json_data else None,
                        headers=headers if headers else None
                    )
                    
                    if result.get("success"):
                        st.success(f"Requête exécutée (Status: {result['details']['status_code']} {result['details']['status_text']})")
                        
                        # Créer des onglets pour organiser les résultats
                        result_tab1, result_tab2, result_tab3 = st.tabs(["Réponse", "Détails", "Requête"])
                        
                        with result_tab1:
                            st.subheader("Réponse")
                            st.json(result.get("response", {}))
                        
                        with result_tab2:
                            st.subheader("Détails de la réponse")
                            details = result.get("details", {})
                            
                            # Afficher le temps de réponse et le code d'état de manière proéminente
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Temps de réponse", f"{details.get('elapsed_ms', 0)} ms")
                            with col2:
                                st.metric("Code HTTP", details.get('status_code', 0))
                            with col3:
                                st.metric("Taille", f"{details.get('content_length', 0)} octets")
                            
                            # Afficher les en-têtes de réponse
                            if verbose_mode:
                                st.subheader("En-têtes de réponse")
                                for key, value in details.get("headers", {}).items():
                                    st.text(f"{key}: {value}")
                        
                        with result_tab3:
                            st.subheader("Détails de la requête")
                            request_info = result.get("request", {})
                            
                            # Afficher l'URL complète
                            st.markdown(f"**URL**: {request_info.get('url')}")
                            st.markdown(f"**Méthode**: {request_info.get('method')}")
                            
                            # Paramètres et corps
                            if request_info.get("params"):
                                st.markdown("**Paramètres de requête:**")
                                st.json(request_info.get("params"))
                            
                            if request_info.get("json"):
                                st.markdown("**Corps de la requête:**")
                                st.json(request_info.get("json"))
                            
                            # En-têtes de requête
                            if verbose_mode and request_info.get("headers"):
                                st.markdown("**En-têtes de requête:**")
                                for key, value in request_info.get("headers", {}).items():
                                    st.text(f"{key}: {value}")
                    else:
                        st.error(f"Erreur lors de l'exécution de la requête: {result.get('error', 'Erreur inconnue')}")
                        
                        # Afficher les détails de l'erreur
                        with st.expander("Détails de l'erreur"):
                            st.text(result.get("traceback", "Pas de traceback disponible"))
                            st.subheader("Informations sur la requête")
                            st.json(result.get("request", {}))
    
    # Test de disponibilité de la base de données
    st.subheader("Test de la base de données")
    if st.button("Vérifier la base de données"):
        with st.spinner("Vérification de la base de données..."):
            # Essayer de récupérer les entrées du journal (pour vérifier l'accès à la DB)
            entries = get_journal_entries(limit=1)
            if entries is not None:
                st.success(f"Accès à la base de données OK, {len(entries)} entrée(s) récupérée(s)")
            else:
                st.error("Impossible d'accéder à la base de données")
    
    # Affichage des logs (si disponibles)
    st.subheader("Logs de l'application")
    
    # Logs frontend
    with st.expander("Logs Frontend (Streamlit)"):
        try:
            # Trouver le fichier de log le plus récent
            logs_dir = Path("logs")
            if logs_dir.exists():
                frontend_logs = list(logs_dir.glob("frontend_*.log"))
                if frontend_logs:
                    latest_log = max(frontend_logs, key=lambda x: x.stat().st_mtime)
                    log_path = latest_log
                else:
                    # Fallback sur le fichier de log standard
                    log_path = logs_dir / "frontend.log"
                
                if log_path.exists():
                    # Lire les 500 dernières lignes pour éviter de charger un fichier trop volumineux
                    with open(log_path, "r") as log_file:
                        lines = log_file.readlines()
                        log_content = "".join(lines[-500:])
                        st.text_area("Contenu des logs Frontend", log_content, height=300)
                        
                        # Option pour télécharger le fichier complet
                        log_content_full = "".join(lines)
                        st.download_button(
                            "Télécharger le fichier de log complet",
                            log_content_full,
                            file_name=log_path.name,
                            mime="text/plain"
                        )
                else:
                    st.warning(f"Fichier de log {log_path} introuvable")
            else:
                st.warning("Répertoire de logs non trouvé")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture des logs frontend: {str(e)}")
            st.error(f"Impossible de lire les logs frontend: {str(e)}")
    
    # Logs backend
    with st.expander("Logs Backend (FastAPI)"):
        try:
            # Trouver le fichier de log le plus récent dans le backend
            backend_logs_dir = Path("../backend/logs")
            if backend_logs_dir.exists():
                backend_logs = list(backend_logs_dir.glob("api_*.log"))
                if backend_logs:
                    latest_log = max(backend_logs, key=lambda x: x.stat().st_mtime)
                    log_path = latest_log
                else:
                    # Fallback sur le fichier de log standard
                    log_path = backend_logs_dir / "api.log"
                
                if log_path.exists():
                    # Lire les 500 dernières lignes pour éviter de charger un fichier trop volumineux
                    with open(log_path, "r") as log_file:
                        lines = log_file.readlines()
                        log_content = "".join(lines[-500:])
                        st.text_area("Contenu des logs Backend", log_content, height=300)
                        
                        # Option pour télécharger le fichier complet
                        log_content_full = "".join(lines)
                        st.download_button(
                            "Télécharger le fichier de log complet",
                            log_content_full,
                            file_name=log_path.name,
                            mime="text/plain"
                        )
                else:
                    st.warning(f"Fichier de log {log_path} introuvable")
            else:
                st.warning("Répertoire de logs backend non trouvé")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture des logs backend: {str(e)}")
            st.error(f"Impossible de lire les logs backend: {str(e)}")
    
    # Informations sur le système de logging
    with st.expander("Informations sur le système de logging"):
        st.write("### Configuration de logging")
        
        # Vérifier si Rich et Loguru sont disponibles
        try:
            import rich
            # Obtenir la version de Rich en utilisant importlib.metadata
            try:
                # Première méthode : utiliser importlib.metadata (Python 3.8+)
                rich_version = importlib.metadata.version("rich")
            except (ImportError, ModuleNotFoundError, Exception):
                try:
                    # Deuxième méthode : utiliser pkg_resources (si disponible)
                    if pkg_resources:
                        rich_version = pkg_resources.get_distribution("rich").version
                    else:
                        raise ImportError("pkg_resources non disponible")
                except Exception:
                    try:
                        # Troisième méthode : vérifier si __version__ existe
                        if hasattr(rich, "__version__"):
                            rich_version = rich.__version__
                        else:
                            # Dernière option : vérifier le module
                            if hasattr(rich, "__file__"):
                                # Afficher le chemin du module comme information de débogage
                                module_path = rich.__file__
                                rich_version = f"installé (chemin: {os.path.dirname(module_path)})"
                            else:
                                rich_version = "version inconnue"
                    except Exception:
                        rich_version = "version inconnue"
            rich_status = f"✅ Installé (v{rich_version})"
        except ImportError:
            rich_status = "❌ Non installé"
        
        try:
            import loguru
            # Obtenir la version de Loguru
            try:
                loguru_version = loguru.__version__
            except AttributeError:
                try:
                    import importlib.metadata
                    loguru_version = importlib.metadata.version("loguru")
                except Exception:
                    loguru_version = "version inconnue"
            loguru_status = f"✅ Installé (v{loguru_version})"
        except ImportError:
            loguru_status = "❌ Non installé"
        
        st.write(f"- Rich: {rich_status}")
        st.write(f"- Loguru: {loguru_status}")
        
        # Niveau de log actuel
        st.write(f"- Niveau de log: {os.environ.get('LOG_LEVEL', 'INFO')}")
        
        # Emplacement des fichiers de log
        st.write("### Fichiers de log")
        st.write("- Frontend: `./logs/frontend_*.log`")
        st.write("- Backend: `../backend/logs/api_*.log`")
        
        # Ajout d'un bouton pour forcer un log de test
        if st.button("Générer des logs de test"):
            logger.debug("Log de test - DEBUG")
            logger.info("Log de test - INFO")
            logger.warning("Log de test - WARNING")
            logger.error("Log de test - ERROR")
            st.success("Logs de test générés avec succès")
    
    # Explorateur de base de données 
    st.subheader("Explorateur de base de données")
    
    # Créer des onglets pour la structure et les requêtes SQL
    db_structure_tab, db_query_tab = st.tabs(["Structure de la base", "Requêtes SQL"])
    
    with db_structure_tab:
        st.write("Cet outil permet d'explorer la structure de la base de données SQLite.")
        
        if st.button("Charger la structure de la base de données"):
            with st.spinner("Récupération de la structure..."):
                db_structure = get_database_structure()
                
                if db_structure:
                    # Sauvegarder dans la session state
                    st.session_state.db_structure = db_structure
                    st.success("Structure de la base de données récupérée avec succès")
                    
                    # Adapter pour gérer les deux formats (Pydantic v1 avec __root__ et v2 avec RootModel)
                    # Si db_structure est un dict, l'utiliser directement, sinon essayer de l'accéder comme un RootModel
                    structure_data = db_structure.root if hasattr(db_structure, 'root') else db_structure
                    
                    # Créer un accordéon pour chaque table
                    for table_name, table_info in structure_data.items():
                        with st.expander(f"Table: {table_name}"):
                            if "columns" in table_info:
                                # Créer un DataFrame pour les colonnes
                                columns_df = pd.DataFrame(table_info["columns"])
                                st.dataframe(columns_df)
                                
                                # Afficher les indices si disponibles
                                if "indices" in table_info and table_info["indices"]:
                                    st.markdown("**Indices:**")
                                    for index in table_info["indices"]:
                                        st.write(f"- {index}")
                                
                                # Afficher les clés étrangères si disponibles
                                if "foreign_keys" in table_info and table_info["foreign_keys"]:
                                    st.markdown("**Clés étrangères:**")
                                    for fk in table_info["foreign_keys"]:
                                        st.write(f"- {fk}")
                                
                                # Bouton pour générer un SELECT * FROM
                                if st.button(f"Query SELECT * FROM {table_name}", key=f"query_{table_name}"):
                                    st.session_state.sql_query = f"SELECT * FROM {table_name} LIMIT 100"
                                    st.experimental_rerun()
                            else:
                                st.warning(f"Aucune information de colonnes disponible pour la table {table_name}")
                else:
                    st.error("Impossible de récupérer la structure de la base de données")
    
    with db_query_tab:
        st.write("Exécutez des requêtes SQL en lecture seule pour déboguer la base de données.")
        
        # Message d'avertissement
        st.warning("⚠️ Attention: Seules les requêtes SQL en lecture seule (SELECT) sont autorisées pour des raisons de sécurité.")
        
        # Champ de requête avec valeur par défaut si présente dans session_state
        default_query = st.session_state.get("sql_query", "SELECT name FROM sqlite_master WHERE type='table'")
        sql_query = st.text_area("Requête SQL", value=default_query, height=150)
        
        # Sauvegarder la requête dans session_state
        st.session_state.sql_query = sql_query
        
        # Exemples de requêtes utiles
        with st.expander("Exemples de requêtes utiles"):
            st.code("-- Liste des tables\nSELECT name FROM sqlite_master WHERE type='table'", language="sql")
            st.code("-- Schéma d'une table\nPRAGMA table_info(journal_entries)", language="sql")
            st.code("-- Nombre d'entrées par type\nSELECT type_entree, COUNT(*) as count FROM journal_entries GROUP BY type_entree", language="sql")
            st.code("-- Entrées récentes\nSELECT id, date, substr(texte, 1, 50) as apercu, type_entree FROM journal_entries ORDER BY date DESC LIMIT 10", language="sql")
            
            # Bouton pour utiliser l'exemple
            if st.button("Utiliser l'exemple sélectionné"):
                # Trouver le code SQL dans l'exemple et l'extraire
                lines = sql_query.split('\n')
                if len(lines) > 1 and lines[0].startswith('--'):
                    st.session_state.sql_query = lines[1]
                    st.experimental_rerun()
        
        # Exécuter la requête
        if st.button("Exécuter la requête", key="execute_sql"):
            with st.spinner("Exécution de la requête SQL..."):
                if not sql_query.lower().strip().startswith('select') and not sql_query.lower().strip().startswith('pragma'):
                    st.error("Seules les requêtes SELECT et PRAGMA sont autorisées.")
                else:
                    result = execute_sql_query(sql_query)
                    
                    if result:
                        st.success("Requête exécutée avec succès")
                        
                        # Afficher les résultats
                        if "rows" in result:
                            rows = result["rows"]
                            
                            if rows:
                                # Convertir en DataFrame pour un meilleur affichage
                                df = pd.DataFrame(rows)
                                st.dataframe(df)
                                
                                # Option pour télécharger les résultats
                                csv = df.to_csv(index=False)
                                st.download_button(
                                    "Télécharger les résultats (CSV)",
                                    csv,
                                    file_name="query_results.csv",
                                    mime="text/csv"
                                )
                                
                                # Statistiques sur les résultats
                                st.markdown(f"**{len(rows)} lignes retournées**")
                                
                                # Analytique simple sur les données numériques
                                if len(rows) > 5:
                                    try:
                                        numeric_cols = df.select_dtypes(include=['number']).columns
                                        if not numeric_cols.empty:
                                            with st.expander("Statistiques sur les données numériques"):
                                                st.write(df[numeric_cols].describe())
                                    except Exception as e:
                                        st.warning(f"Impossible de générer des statistiques: {str(e)}")
                            else:
                                st.info("La requête n'a retourné aucune ligne.")
                        else:
                            st.warning("Format de réponse inattendu.")
                    else:
                        st.error("Erreur lors de l'exécution de la requête SQL")
    
    # Outil de réinitialisation
    st.subheader("Outils de réinitialisation")
    if st.button("Réinitialiser le mode de débogage"):
        # Stocker dans la session le réglage du mode débogage
        if 'debug_mode' not in st.session_state:
            st.session_state.debug_mode = True
        else:
            st.session_state.debug_mode = not st.session_state.debug_mode
        
        st.success(f"Mode débogage {'activé' if st.session_state.debug_mode else 'désactivé'}")
        st.info("Actualisez la page pour que les changements prennent effet")