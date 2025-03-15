import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import time
import tempfile
import os.path

# Configuration de l'API
API_URL = os.environ.get("API_URL", "http://localhost:8000")

# Configuration de Streamlit
st.set_page_config(
    page_title="Agent Mémoire Alternance",
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
</style>
""", unsafe_allow_html=True)

# --- Fonctions d'appel à l'API avec gestion d'erreurs améliorée ---
def api_request(method, endpoint, **kwargs):
    """
    Fonction améliorée pour les requêtes API avec gestion d'erreurs robuste
    """
    max_retries = 3
    retry_delay = 1
    
    for retry in range(max_retries):
        try:
            url = f"{API_URL}/{endpoint}"
            response = method(url, **kwargs, timeout=10)  # Ajouter un timeout explicite
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

# --- Fonctions existantes d'interrogation de l'API ---
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

def generate_plan(prompt):
    return api_request(requests.post, "ai/generate-plan", json={"prompt": prompt})

def generate_content(section_id, prompt=None):
    data = {"section_id": section_id}
    if prompt:
        data["prompt"] = prompt
    return api_request(requests.post, "ai/generate-content", json=data)

def improve_text(texte, mode):
    return api_request(requests.post, "ai/improve-text", json={"texte": texte, "mode": mode})

def search_entries(query):
    result = api_request(requests.get, "search", params={"query": query})
    if result is None:
        return []
    return result

# --- Nouvelles fonctions pour les nouveaux endpoints ---

# 1. Génération en mode streaming (pour les réponses longues)
def generate_content_streaming(section_id, prompt=None):
    data = {"section_id": section_id}
    if prompt:
        data["prompt"] = prompt
    try:
        url = f"{API_URL}/ai/generate-content-stream"
        with requests.post(url, json=data, stream=True, timeout=600) as response:
            response.raise_for_status()
            content_placeholder = st.empty()
            content_text = ""
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            text_chunk = chunk["response"]
                            content_text += text_chunk
                            content_placeholder.text_area("Contenu généré en streaming", content_text, height=300)
                    except json.JSONDecodeError:
                        continue
            return content_text
    except Exception as e:
        st.error(f"Erreur lors de la génération en streaming: {str(e)}")
        return None

# 2. Gestion des références bibliographiques
def get_references():
    result = api_request(requests.get, "bibliography")
    if result is None:
        return []
    return result

def add_reference(ref_data):
    return api_request(requests.post, "bibliography", json=ref_data)

# 3. Export PDF/Word avec style académique
def export_memory(format="pdf"):
    try:
        response = requests.post(f"{API_URL}/export", json={"format": format})
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Erreur lors de l'exportation: {str(e)}")
        return None

# 4. Sauvegarde et restauration des données
def create_backup(description=None):
    data = {}
    if description:
        data["description"] = description
    return api_request(requests.post, "backup/create", json=data)

def restore_backup(backup_id):
    return api_request(requests.post, f"backup/restore/{backup_id}", json={})

# 5. Cache des embeddings
def get_embedding_cache_status():
    return api_request(requests.get, "embeddings/cache-status")

def clear_embedding_cache():
    return api_request(requests.delete, "embeddings/cache-clear")

# 6. Statut du Circuit Breaker
def get_circuit_breaker_status():
    return api_request(requests.get, "circuit-breaker/status")

# 7. Fonctions d'import de PDF (inchangées)
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

# --- Sidebar - Navigation ---
with st.sidebar:
    st.title("Agent Mémoire")
    st.subheader("Navigation")
    page = st.radio("", ["Tableau de bord", "Journal de bord", "Éditeur de mémoire", "Chat assistant", "Import PDF", "Admin & Outils"])

# --- Pages ---
if page == "Tableau de bord":
    st.markdown("<h1 class='main-title'>Tableau de bord</h1>", unsafe_allow_html=True)
    # (Code existant pour afficher statistiques et entrées récentes)
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
        sections_with_content = sum(1 for s in sections if s.get("contenu"))
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
            text_preview = entry["texte"][:200] + "..." if len(entry["texte"]) > 200 else entry["texte"]
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

    # (Onglets pour consulter et rechercher restent inchangés)

elif page == "Éditeur de mémoire":
    st.markdown("<h1 class='main-title'>Éditeur de mémoire</h1>", unsafe_allow_html=True)
    # (Code existant pour la gestion des sections du mémoire)

elif page == "Chat assistant":
    st.markdown("<h1 class='main-title'>Chat Assistant</h1>", unsafe_allow_html=True)
    streaming = st.checkbox("Utiliser le streaming des réponses longues")
    section_id = st.text_input("Section ID", "section-1")
    prompt = st.text_area("Votre prompt", "Entrez votre demande ici...")
    if st.button("Générer du contenu"):
        if streaming:
            st.info("Génération en streaming...")
            generated = generate_content_streaming(section_id, prompt)
            st.text_area("Contenu généré", generated, height=300)
        else:
            generated = generate_content(section_id, prompt)
            st.text_area("Contenu généré", generated, height=300)

elif page == "Import PDF":
    st.markdown("<h1 class='main-title'>Import PDF</h1>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Choisissez un fichier PDF", type=["pdf"])
    if uploaded_file is not None:
        if st.button("Analyser le PDF"):
            analysis = analyze_pdf(uploaded_file)
            if analysis:
                st.json(analysis)
        if st.button("Importer le PDF"):
            entreprises = get_entreprises()
            entreprise_options = {e["nom"]: e["id"] for e in entreprises}
            entreprise = st.selectbox("Entreprise pour l'import", list(entreprise_options.keys()))
            result = import_pdf(uploaded_file, entreprise_id=entreprise_options[entreprise])
            if result:
                st.success("PDF importé et entrées créées.")

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
    
    # Références bibliographiques
    st.subheader("Références Bibliographiques")
    references = get_references()
    if references:
        df_refs = pd.DataFrame(references)
        st.dataframe(df_refs)
    with st.expander("Ajouter une nouvelle référence"):
        ref_title = st.text_input("Titre")
        ref_authors = st.text_input("Auteurs")
        ref_year = st.number_input("Année", min_value=1900, max_value=datetime.now().year, step=1)
        ref_publisher = st.text_input("Éditeur")
        if st.button("Ajouter la référence"):
            ref_data = {
                "title": ref_title,
                "authors": ref_authors,
                "year": ref_year,
                "publisher": ref_publisher
            }
            result = add_reference(ref_data)
            if result:
                st.success("Référence ajoutée avec succès.")
    st.markdown("---")
    
    # Export du mémoire
    st.subheader("Export du Mémoire")
    export_format = st.selectbox("Format d'export", ["pdf", "docx"])
    if st.button("Exporter"):
        export_data = export_memory(export_format)
        if export_data:
            st.download_button(
                label=f"Télécharger le mémoire au format {export_format.upper()}",
                data=export_data,
                file_name=f"memoire_export.{export_format}",
                mime="application/pdf" if export_format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
    st.markdown("---")
    
    # Sauvegarde et restauration
    st.subheader("Sauvegarde et Restauration")
    if st.button("Créer une sauvegarde"):
        description = st.text_input("Description de la sauvegarde", "Sauvegarde manuelle")
        backup_result = create_backup(description)
        if backup_result:
            st.success("Sauvegarde créée avec succès.")
    st.markdown("### Restaurer une sauvegarde")
    backup_id = st.text_input("ID de la sauvegarde à restaurer")
    if st.button("Restaurer la sauvegarde"):
        restore_result = restore_backup(backup_id)
        if restore_result:
            st.success("Sauvegarde restaurée avec succès.")
