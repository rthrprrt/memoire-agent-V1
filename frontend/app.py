import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import time
import tempfile

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
    """Fonction pour les requêtes API avec gestion d'erreurs robuste"""
    max_retries = 3
    retry_delay = 1
    
    for retry in range(max_retries):
        try:
            url = f"{API_URL}/{endpoint}"
            response = method(url, **kwargs, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            if retry < max_retries - 1:
                st.warning(f"Tentative de connexion {retry+1}/{max_retries} échouée. Nouvelle tentative dans {retry_delay} secondes...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponentiel
            else:
                st.error(f"Impossible de se connecter à l'API ({API_URL}) après {max_retries} tentatives.")
                # Essayer alternatives si on n'est pas déjà en train de tester une URL alternative
                if API_URL != "http://localhost:8000":
                    try:
                        st.info("Tentative avec URL alternative: http://localhost:8000")
                        url = f"http://localhost:8000/{endpoint}"
                        response = method(url, **kwargs, timeout=10)
                        response.raise_for_status()
                        return response.json()
                    except:
                        pass
                return None
        except requests.exceptions.Timeout:
            if retry < max_retries - 1:
                st.warning(f"Délai d'attente dépassé (tentative {retry+1}/{max_retries}). Nouvelle tentative dans {retry_delay} secondes...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                st.error("Délai d'attente dépassé lors de la connexion à l'API.")
                return None
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_msg = f"Erreur HTTP {status_code}"
            try:
                error_detail = e.response.json().get("detail", "Pas de détails disponibles")
                error_msg += f": {error_detail}"
            except:
                pass
            st.error(error_msg)
            return None
        except Exception as e:
            st.error(f"Erreur inattendue: {str(e)}")
            return None

# --- Fonctions d'interrogation de l'API pour le journal ---
def get_entreprises():
    result = api_request(requests.get, "entreprises")
    if result is None:
        return [{"id": 1, "nom": "Entreprise par défaut", "date_debut": "2023-09-01", "date_fin": None}]
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

def analyze_pdf(uploaded_file):
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        response = requests.post(f"{API_URL}/import/pdf/analyze", files=files)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'analyse du PDF: {str(e)}")
        return None

def import_pdf(uploaded_file, entreprise_id=None):
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        data = {}
        if entreprise_id:
            data["entreprise_id"] = str(entreprise_id)
        response = requests.post(f"{API_URL}/import/pdf", files=files, data=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'import du PDF: {str(e)}")
        return None

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

# --- Interface utilisateur ---
with st.sidebar:
    st.title("Assistant Mémoire")
    st.subheader("Navigation")
    page = st.radio("", ["Tableau de bord", "Journal de bord", "Éditeur de mémoire", "Chat assistant", "Import PDF", "Admin & Outils"])

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

elif page == "Import PDF":
    st.markdown("<h1 class='main-title'>Import PDF</h1>", unsafe_allow_html=True)
    st.write("Importez des fichiers PDF pour extraire automatiquement des entrées de journal.")
    
    uploaded_file = st.file_uploader("Choisissez un fichier PDF", type=["pdf"])
    if uploaded_file is not None:
        st.write(f"Fichier chargé: {uploaded_file.name}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Analyser le PDF"):
                with st.spinner("Analyse en cours..."):
                    analysis = analyze_pdf(uploaded_file)
                    if analysis:
                        st.success(f"Analyse terminée. {len(analysis)} entrées potentielles trouvées.")
                        st.json(analysis)
        
        with col2:
            entreprises = get_entreprises()
            entreprise_options = {e["nom"]: e["id"] for e in entreprises}
            entreprise = st.selectbox("Entreprise pour l'import", list(entreprise_options.keys()))
            
            if st.button("Importer le PDF"):
                with st.spinner("Import en cours..."):
                    result = import_pdf(uploaded_file, entreprise_id=entreprise_options[entreprise])
                    if result:
                        st.success(f"PDF importé. {len(result.get('entries', []))} entrées créées.")
                        
                        # Option pour vérifier les hallucinations dans le contenu importé
                        if st.checkbox("Vérifier les hallucinations dans le contenu importé"):
                            for i, entry in enumerate(result.get('entries', [])):
                                st.write(f"Vérification de l'entrée {i+1}...")
                                verification = verify_content(entry.get('texte', ''))
                                if verification and verification.get("has_hallucinations"):
                                    st.warning(f"Hallucinations détectées dans l'entrée {i+1}")
                                    for segment in verification["suspect_segments"]:
                                        st.markdown(f"<div class='suspect-segment'>{segment['text']}</div>", unsafe_allow_html=True)

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