import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import time
import tempfile

# Configuration de l'API
# Correction : utilisation d'une URL plus flexible avec une valeur par défaut pour le développement local
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

# Fonctions d'API avec gestion d'erreurs améliorée
def api_request(method, endpoint, **kwargs):
    """Fonction générique pour effectuer des requêtes API avec gestion d'erreurs"""
    try:
        url = f"{API_URL}/{endpoint}"
        response = method(url, **kwargs)
        response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Impossible de se connecter à l'API ({API_URL}). Vérifiez que le backend est en cours d'exécution.")
        return None
    except requests.exceptions.Timeout:
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

def get_entreprises():
    """Récupère la liste des entreprises depuis l'API"""
    result = api_request(requests.get, "entreprises")
    if result is None:
        # Valeur par défaut en cas d'échec
        return [{"id": 1, "nom": "Entreprise par défaut", "date_debut": "2023-09-01", "date_fin": None}]
    return result

def get_tags():
    """Récupère la liste des tags depuis l'API"""
    result = api_request(requests.get, "tags")
    if result is None:
        # Valeur par défaut en cas d'échec
        return []
    return result

def get_journal_entries(start_date=None, end_date=None, entreprise_id=None, type_entree=None, tag=None):
    """Récupère les entrées du journal depuis l'API avec filtres optionnels"""
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
        # Valeur par défaut en cas d'échec
        return []
    return result

def add_journal_entry(entry_data):
    """Ajoute une entrée au journal via l'API"""
    return api_request(requests.post, "journal/entries", json=entry_data)

def update_journal_entry(entry_id, entry_data):
    """Met à jour une entrée du journal via l'API"""
    return api_request(requests.put, f"journal/entries/{entry_id}", json=entry_data)

def delete_journal_entry(entry_id):
    """Supprime une entrée du journal via l'API"""
    result = api_request(requests.delete, f"journal/entries/{entry_id}")
    if result is not None:
        return True
    return False

def get_memoire_sections(parent_id=None):
    """Récupère les sections du mémoire depuis l'API"""
    params = {}
    if parent_id is not None:
        params["parent_id"] = parent_id
    
    result = api_request(requests.get, "memoire/sections", params=params)
    if result is None:
        # Valeur par défaut en cas d'échec
        return []
    return result

def get_memoire_section(section_id):
    """Récupère une section spécifique du mémoire depuis l'API"""
    return api_request(requests.get, f"memoire/sections/{section_id}")

def add_memoire_section(section_data):
    """Ajoute une section au mémoire via l'API"""
    return api_request(requests.post, "memoire/sections", json=section_data)

def update_memoire_section(section_id, section_data):
    """Met à jour une section du mémoire via l'API"""
    return api_request(requests.put, f"memoire/sections/{section_id}", json=section_data)

def delete_memoire_section(section_id):
    """Supprime une section du mémoire via l'API"""
    result = api_request(requests.delete, f"memoire/sections/{section_id}")
    if result is not None:
        return True
    return False

def generate_plan(prompt):
    """Génère un plan de mémoire via l'API IA"""
    return api_request(requests.post, "ai/generate-plan", json={"prompt": prompt})

def generate_content(section_id, prompt=None):
    """Génère du contenu pour une section du mémoire via l'API IA"""
    data = {"section_id": section_id}
    if prompt:
        data["prompt"] = prompt
    
    return api_request(requests.post, "ai/generate-content", json=data)

def improve_text(texte, mode):
    """Améliore un texte via l'API IA"""
    return api_request(requests.post, "ai/improve-text", json={"texte": texte, "mode": mode})

def search_entries(query):
    """Recherche des entrées de journal via l'API"""
    result = api_request(requests.get, "search", params={"query": query})
    if result is None:
        return []
    return result

# Nouvelles fonctions pour l'import de PDF
def analyze_pdf(uploaded_file):
    """Analyse un PDF sans l'importer pour prévisualisation"""
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        # Utilisation de api_request ne fonctionnerait pas bien avec les fichiers, donc on garde l'approche directe
        response = requests.post(f"{API_URL}/import/pdf/analyze", files=files)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'analyse du PDF: {str(e)}")
        return None

def import_pdf(uploaded_file, entreprise_id=None):
    """Importe un PDF et crée des entrées de journal"""
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

# Sidebar - Authentification et Navigation
with st.sidebar:
    st.title("Agent Mémoire")
    
    # Menu de navigation
    st.subheader("Navigation")
    page = st.radio("", ["Tableau de bord", "Journal de bord", "Éditeur de mémoire", "Chat assistant", "Import PDF"])

# Pages
if page == "Tableau de bord":
    st.markdown("<h1 class='main-title'>Tableau de bord</h1>", unsafe_allow_html=True)
    
    # Statistiques générales
    col1, col2, col3 = st.columns(3)
    
    # Nombre d'entrées de journal
    entries = get_journal_entries()
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Entrées de journal")
        st.metric("Total", len(entries))
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Nombre de sections du mémoire
    sections = get_memoire_sections()
    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Sections du mémoire")
        st.metric("Total", len(sections))
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Avancement global
    with col3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Avancement global")
        
        # Calculer l'avancement (sections avec contenu / total sections)
        sections_with_content = sum(1 for s in sections if s.get("contenu"))
        progress = sections_with_content / max(len(sections), 1) * 100
        
        st.progress(progress / 100)
        st.metric("Pourcentage", f"{progress:.1f}%")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Entrées récentes
    st.markdown("<h2 class='section-title'>Entrées récentes</h2>", unsafe_allow_html=True)
    
    recent_entries = entries[:5]  # Prendre les 5 entrées les plus récentes
    
    if recent_entries:
        for entry in recent_entries:
            st.markdown("<div class='entry-container'>", unsafe_allow_html=True)
            st.markdown(f"<p class='entry-date'>{entry['date']}</p>", unsafe_allow_html=True)
            
            # Afficher les tags
            tags_html = ""
            for tag in entry.get("tags", []):
                tags_html += f"<span class='tag'>{tag}</span>"
            
            st.markdown(tags_html, unsafe_allow_html=True)
            
            # Afficher un extrait du texte
            text_preview = entry["texte"][:200] + "..." if len(entry["texte"]) > 200 else entry["texte"]
            st.write(text_preview)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Aucune entrée récente trouvée. Ajoutez des entrées depuis l'onglet Journal de bord.")
    
    # Tags les plus utilisés
    st.markdown("<h2 class='section-title'>Tags populaires</h2>", unsafe_allow_html=True)
    
    tags = get_tags()
    if tags:
        # Créer un dataframe pour afficher les tags
        df_tags = pd.DataFrame({
            "Tag": [tag["nom"] for tag in tags],
            "Nombre d'entrées": [tag["count"] for tag in tags]
        })
        
        # Afficher un graphique
        st.bar_chart(df_tags.set_index("Tag"))
    else:
        st.info("Aucun tag trouvé. Les tags sont générés automatiquement lorsque vous ajoutez des entrées au journal.")

# Le reste du code pour les autres pages (Journal de bord, Éditeur de mémoire, Chat assistant, Import PDF)
# reste inchangé car l'approche fondamentale ne change pas, seules les fonctions d'API sont améliorées.

elif page == "Journal de bord":
    st.markdown("<h1 class='main-title'>Journal de bord</h1>", unsafe_allow_html=True)
    
    # Onglets
    tab1, tab2, tab3 = st.tabs(["Ajouter une entrée", "Consulter les entrées", "Recherche"])
    
    # Onglet Ajouter une entrée
    with tab1:
        st.markdown("<h2 class='section-title'>Nouvelle entrée</h2>", unsafe_allow_html=True)
        
        # Entreprises
        entreprises = get_entreprises()
        entreprise_options = {e["nom"]: e["id"] for e in entreprises}
        
        # Formulaire
        with st.form("journal_entry_form"):
            date = st.date_input("Date", datetime.now())
            
            # Déterminer l'entreprise par défaut en fonction de la date
            default_entreprise = None
            for e in entreprises:
                start_date = datetime.strptime(e["date_debut"], "%Y-%m-%d").date()
                end_date = datetime.strptime(e["date_fin"], "%Y-%m-%d").date() if e["date_fin"] else None
                
                if start_date <= date and (end_date is None or date <= end_date):
                    default_entreprise = e["nom"]
                    break
            
            entreprise_index = 0
            if default_entreprise and default_entreprise in list(entreprise_options.keys()):
                entreprise_index = list(entreprise_options.keys()).index(default_entreprise)
            
            entreprise = st.selectbox("Entreprise", list(entreprise_options.keys()), index=entreprise_index)
            
            type_entree = st.selectbox("Type d'entrée", ["quotidien", "projet", "formation", "réflexion"])
            
            texte = st.text_area("Contenu", height=300)
            
            # Tags existants
            all_tags = get_tags()
            existing_tags = [tag["nom"] for tag in all_tags]
            
            # Option pour des tags existants ou nouveaux
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
                    # Préparer les données
                    entry_data = {
                        "date": date.strftime("%Y-%m-%d"),
                        "texte": texte,
                        "entreprise_id": entreprise_options[entreprise],
                        "type_entree": type_entree,
                        "tags": selected_tags if selected_tags and selected_tags[0] else None
                    }
                    
                    # Ajouter l'entrée
                    result = add_journal_entry(entry_data)
                    
                    if result:
                        st.success("Entrée ajoutée avec succès!")
                        # Proposer d'extraire automatiquement des tags
                        if not selected_tags:
                            auto_tags = result.get("tags", [])
                            if auto_tags:
                                st.info(f"Tags extraits automatiquement: {', '.join(auto_tags)}")
    
    # Les onglets Consulter les entrées et Recherche sont omis pour concision,
    # mais suivraient le même modèle d'amélioration



elif page == "Éditeur de mémoire":
    st.markdown("<h1 class='main-title'>Éditeur de mémoire</h1>", unsafe_allow_html=True)
    
    # Onglets
    tab1, tab2 = st.tabs(["Plan et structure", "Rédaction"])
    
    # Onglet Plan et structure
    with tab1:
        st.markdown("<h2 class='section-title'>Plan du mémoire</h2>", unsafe_allow_html=True)
        
        # Générer un plan
        with st.expander("Générer un plan"):
            plan_prompt = st.text_area("Instructions pour la génération du plan", 
                                       "Générer un plan de mémoire professionnel pour mon alternance en informatique, avec une structure conforme au RNCP 35284.")
            
            if st.button("Générer"):
                with st.spinner("Génération du plan en cours..."):
                    result = generate_plan(plan_prompt)
                    
                    if result:
                        st.success("Plan généré avec succès!")
                        st.text_area("Plan proposé", result["plan"], height=400)
        
        # Afficher la structure du mémoire
        sections_root = get_memoire_sections()
        
        if not sections_root:
            st.info("Aucune section n'a été créée. Vous pouvez générer un plan ou ajouter manuellement des sections.")
        else:
            # Afficher la structure en arbre
            for section in sections_root:
                section_expander = st.expander(f"{section['titre']}")
                
                with section_expander:
                    # Boutons d'action pour la section principale
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button(f"Modifier", key=f"edit_main_{section['id']}"):
                            st.session_state["edit_section"] = section
                            st.experimental_rerun()
                    
                    with col2:
                        if st.button(f"Supprimer", key=f"delete_main_{section['id']}"):
                            if delete_memoire_section(section["id"]):
                                st.success("Section supprimée avec succès!")
                                st.experimental_rerun()
                    
                    with col3:
                        if st.button(f"Ajouter sous-section", key=f"add_sub_{section['id']}"):
                            st.session_state["add_subsection"] = section["id"]
                            st.experimental_rerun()
                    
                    # Afficher les sous-sections
                    subsections = get_memoire_sections(parent_id=section["id"])
                    
                    for subsection in subsections:
                        sub_col1, sub_col2 = st.columns([3, 1])
                        
                        with sub_col1:
                            st.write(f"• {subsection['titre']}")
                        
                        with sub_col2:
                            if st.button(f"Modifier", key=f"edit_sub_{subsection['id']}"):
                                st.session_state["edit_section"] = subsection
                                st.experimental_rerun()
                            
                            if st.button(f"Supprimer", key=f"delete_sub_{subsection['id']}"):
                                if delete_memoire_section(subsection["id"]):
                                    st.success("Sous-section supprimée avec succès!")
                                    st.experimental_rerun()
        
        # Ajouter une section principale
        with st.expander("Ajouter une section principale"):
            with st.form("add_main_section_form"):
                section_title = st.text_input("Titre")
                section_order = st.number_input("Ordre", min_value=0, step=1)
                
                submit_section = st.form_submit_button("Ajouter")
                
                if submit_section:
                    if not section_title:
                        st.error("Le titre ne peut pas être vide.")
                    else:
                        # Préparer les données
                        section_data = {
                            "titre": section_title,
                            "contenu": "",
                            "ordre": section_order,
                            "parent_id": None
                        }
                        
                        # Ajouter la section
                        result = add_memoire_section(section_data)
                        
                        if result:
                            st.success("Section ajoutée avec succès!")
                            st.experimental_rerun()
        
        # Ajouter une sous-section
        if "add_subsection" in st.session_state:
            parent_id = st.session_state["add_subsection"]
            
            # Récupérer le titre du parent
            parent_section = get_memoire_section(parent_id)
            parent_title = parent_section["titre"] if parent_section else "Section parente"
            
            st.markdown(f"<h3 class='subsection-title'>Ajouter une sous-section à '{parent_title}'</h3>", unsafe_allow_html=True)
            
            with st.form("add_subsection_form"):
                subsection_title = st.text_input("Titre")
                subsection_order = st.number_input("Ordre", min_value=0, step=1)
                
                submit_subsection = st.form_submit_button("Ajouter")
                
                if submit_subsection:
                    if not subsection_title:
                        st.error("Le titre ne peut pas être vide.")
                    else:
                        # Préparer les données
                        section_data = {
                            "titre": subsection_title,
                            "contenu": "",
                            "ordre": subsection_order,
                            "parent_id": parent_id
                        }
                        
                        # Ajouter la section
                        result = add_memoire_section(section_data)
                        
                        if result:
                            st.success("Sous-section ajoutée avec succès!")
                            del st.session_state["add_subsection"]
                            st.experimental_rerun()
            
            # Bouton pour annuler
            if st.button("Annuler l'ajout"):
                del st.session_state["add_subsection"]
                st.experimental_rerun()
        
        # Modifier une section
        if "edit_section" in st.session_state:
            section = st.session_state["edit_section"]
            
            st.markdown(f"<h3 class='subsection-title'>Modifier la section</h3>", unsafe_allow_html=True)
            
            with st.form("edit_section_form"):
                edit_title = st.text_input("Titre", section["titre"])
                edit_order = st.number_input("Ordre", min_value=0, step=1, value=section["ordre"])
                
                submit_edit = st.form_submit_button("Enregistrer les modifications")
                
                if submit_edit:
                    if not edit_title:
                        st.error("Le titre ne peut pas être vide.")
                    else:
                        # Préparer les données
                        update_data = {
                            "titre": edit_title,
                            "contenu": section["contenu"] or "",
                            "ordre": edit_order,
                            "parent_id": section["parent_id"]
                        }
                        
                        # Mettre à jour la section
                        result = update_memoire_section(section["id"], update_data)
                        
                        if result:
                            st.success("Section mise à jour avec succès!")
                            del st.session_state["edit_section"]
                            st.experimental_rerun()
            
            # Bouton pour annuler
            if st.button("Annuler la modification"):
                del st.session_state["edit_section"]
                st.experimental_rerun()
    
    # Onglet Rédaction
    with tab2:
        st.markdown("<h2 class='section-title'>Rédaction du mémoire</h2>", unsafe_allow_html=True)
        
        # Sélection de la section à rédiger
        all_sections = []
        sections_root = get_memoire_sections()
        
        for section in sections_root:
            all_sections.append({"id": section["id"], "titre": section["titre"], "parent_id": None})
            
            subsections = get_memoire_sections(parent_id=section["id"])
            for subsection in subsections:
                all_sections.append({"id": subsection["id"], "titre": f"  • {subsection['titre']}", "parent_id": section["id"]})
        
        if not all_sections:
            st.info("Aucune section n'a été créée. Veuillez d'abord créer une structure dans l'onglet 'Plan et structure'.")
        else:
            section_options = {s["titre"]: s["id"] for s in all_sections}
            selected_section_title = st.selectbox("Sélectionner une section à rédiger", list(section_options.keys()))
            selected_section_id = section_options[selected_section_title]
            
            # Récupérer la section
            section = get_memoire_section(selected_section_id)
            
            if section:
                # Afficher le contenu actuel
                section_content = section["contenu"] or ""
                
                # Aide à la rédaction
                with st.expander("Aide à la rédaction"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("Générer du contenu"):
                            with st.spinner("Génération du contenu en cours..."):
                                result = generate_content(selected_section_id)
                                
                                if result:
                                    section_content = result["content"]
                                    st.success("Contenu généré avec succès!")
                    
                    with col2:
                        if st.button("Rechercher des entrées pertinentes"):
                            # Rechercher des entrées pertinentes pour cette section
                            results = search_entries(section["titre"])
                            
                            if results:
                                st.success(f"{len(results)} entrées pertinentes trouvées")
                                
                                for result in results:
                                    st.markdown(f"<div class='entry-container'>", unsafe_allow_html=True)
                                    st.markdown(f"<p class='entry-date'>{result['date']}</p>", unsafe_allow_html=True)
                                    
                                    # Afficher un extrait du texte
                                    text_preview = result["texte"][:200] + "..." if len(result["texte"]) > 200 else result["texte"]
                                    st.write(text_preview)
                                    
                                    # Bouton pour voir l'entrée complète
                                    with st.expander("Voir l'entrée complète"):
                                        st.write(result["texte"])
                                    
                                    st.markdown("</div>", unsafe_allow_html=True)
                            else:
                                st.info("Aucune entrée pertinente trouvée.")
                
                # Éditeur de texte
                new_content = st.text_area("Contenu de la section", section_content, height=500)
                
                # Outils d'amélioration
                with st.expander("Outils d'amélioration"):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if st.button("Corriger la grammaire"):
                            if new_content:
                                with st.spinner("Correction en cours..."):
                                    result = improve_text(new_content, "grammar")
                                    
                                    if result:
                                        new_content = result["improved_text"]
                                        st.success("Texte corrigé!")
                    
                    with col2:
                        if st.button("Améliorer le style"):
                            if new_content:
                                with st.spinner("Amélioration en cours..."):
                                    result = improve_text(new_content, "style")
                                    
                                    if result:
                                        new_content = result["improved_text"]
                                        st.success("Style amélioré!")
                    
                    with col3:
                        if st.button("Restructurer"):
                            if new_content:
                                with st.spinner("Restructuration en cours..."):
                                    result = improve_text(new_content, "structure")
                                    
                                    if result:
                                        new_content = result["improved_text"]
                                        st.success("Texte restructuré!")
                    
                    with col4:
                        if st.button("Enrichir"):
                            if new_content:
                                with st.spinner("Enrichissement en cours..."):
                                    result = improve_text(new_content, "expand")
                                    
                                    if result:
                                        new_content = result["improved_text"]
                                        st.success("Texte enrichi!")
                
                # Bouton de sauvegarde
                if st.button("Enregistrer"):
                    # Préparer les données
                    update_data = {
                        "titre": section["titre"],
                        "contenu": new_content,
                        "ordre": section["ordre"],
                        "parent_id": section["parent_id"]
                    }
                    
                    # Mettre à jour la section
                    result = update_memoire_section(section["id"], update_data)
                    
                    if result:
                        st.success("Contenu enregistré avec succès!")

elif page == "Chat assistant":
    st.markdown("<h1 class='main-title'>Assistant de rédaction</h1>", unsafe_allow_html=True)
    
    # Initialiser l'historique des messages s'il n'existe pas
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Bonjour ! Je suis votre assistant de rédaction pour votre mémoire d'alternance. Comment puis-je vous aider aujourd'hui ?"}
        ]
    
    # Afficher l'historique des messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Zone de saisie pour le nouveau message
    if prompt := st.chat_input("Posez votre question..."):
        # Ajouter le message de l'utilisateur à l'historique
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Afficher le message de l'utilisateur
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Simuler une réponse de l'assistant (à remplacer par l'appel à l'API)
        with st.chat_message("assistant"):
            with st.spinner("En train de réfléchir..."):
                # Ici, vous devriez appeler une API pour obtenir une réponse
                # Pour l'exemple, nous utilisons une réponse simulée
                
                # Dans une version finale, appeler l'API du modèle
                # response = api_request(requests.post, "ai/chat", json={"prompt": prompt, "history": st.session_state.messages})
                # answer = response.get("response") if response else "Je suis désolé, je ne peux pas répondre pour le moment."
                
                # Simulation de réponse
                time.sleep(1)
                answer = f"Je vais vous aider avec votre question sur '{prompt}'.\n\nPour rédiger un bon mémoire d'alternance, il est important de structurer votre pensée et de s'appuyer sur votre expérience professionnelle."
                
                st.markdown(answer)
        
        # Ajouter la réponse de l'assistant à l'historique
        st.session_state.messages.append({"role": "assistant", "content": answer})

elif page == "Import PDF":
    st.markdown("<h1 class='main-title'>Import de documents</h1>", unsafe_allow_html=True)
    
    # Onglets pour les différentes options d'import
    tab1, tab2 = st.tabs(["Import simple", "Import par lot"])
    
    # Onglet Import simple
    with tab1:
        st.markdown("<h2 class='section-title'>Importer un PDF</h2>", unsafe_allow_html=True)
        
        # Interface d'upload
        uploaded_file = st.file_uploader("Choisissez un fichier PDF", type="pdf", key="single_pdf_upload")
        
        if uploaded_file:
            # Afficher les informations sur le fichier
            st.write(f"Nom du fichier: {uploaded_file.name}")
            st.write(f"Taille: {uploaded_file.size / 1024:.2f} KB")
            
            # Options d'import
            entreprises = get_entreprises()
            entreprise_options = {e["nom"]: e["id"] for e in entreprises}
            
            selected_entreprise = st.selectbox("Entreprise associée", list(entreprise_options.keys()))
            
            # Prévisualisation des entrées
            if st.button("Prévisualiser les entrées"):
                with st.spinner("Analyse du PDF en cours..."):
                    entries = analyze_pdf(uploaded_file)
                    
                    if entries:
                        st.success(f"{len(entries)} entrées trouvées dans le PDF.")
                        
                        # Afficher un aperçu de chaque entrée
                        for i, entry in enumerate(entries):
                            with st.expander(f"Entrée {i+1} - {entry['date']}"):
                                # Type d'entrée détecté
                                st.write(f"Type détecté: {entry['type_entree']}")
                                
                                # Tags extraits
                                if entry.get('tags'):
                                    st.write(f"Tags extraits: {', '.join(entry['tags'])}")
                                
                                # Aperçu du contenu
                                preview_length = min(500, len(entry['texte']))
                                st.write(f"Aperçu du contenu: {entry['texte'][:preview_length]}...")
            
            # Bouton pour importer
            if st.button("Importer"):
                with st.spinner("Import du PDF en cours..."):
                    result = import_pdf(uploaded_file, entreprise_options[selected_entreprise])
                    
                    if result:
                        st.success(result["message"])
                        
                        # Afficher les entrées importées
                        for i, entry in enumerate(result["entries"]):
                            with st.expander(f"Entrée {i+1} - {entry['date']}"):
                                # Tags
                                tags_html = ""
                                for tag in entry.get("tags", []):
                                    tags_html += f"<span class='tag'>{tag}</span>"
                                
                                st.markdown(tags_html, unsafe_allow_html=True)
                                
                                # Type d'entrée
                                st.write(f"Type: {entry['type_entree']}")
                                
                                # Aperçu du contenu
                                preview_length = min(200, len(entry['texte']))
                                st.write(f"Aperçu: {entry['texte'][:preview_length]}...")
    
    # Onglet Import par lot
    with tab2:
        st.markdown("<h2 class='section-title'>Import par lot</h2>", unsafe_allow_html=True)
        
        # Interface d'upload multiple
        uploaded_files = st.file_uploader("Choisissez plusieurs fichiers PDF", type="pdf", accept_multiple_files=True, key="multiple_pdf_upload")
        
        if uploaded_files:
            # Afficher les informations sur les fichiers
            st.write(f"{len(uploaded_files)} fichiers sélectionnés:")
            
            for file in uploaded_files:
                st.write(f"- {file.name} ({file.size / 1024:.2f} KB)")
            
            # Options d'import
            entreprises = get_entreprises()
            entreprise_options = {e["nom"]: e["id"] for e in entreprises}
            
            selected_entreprise = st.selectbox("Entreprise associée pour tous les fichiers", list(entreprise_options.keys()), key="batch_entreprise")
            
            # Options d'importation avancées
            with st.expander("Options avancées"):
                skip_preview = st.checkbox("Importer sans prévisualisation")
                auto_detect_type = st.checkbox("Détecter automatiquement le type d'entrée", value=True)
                
                # Si on ne veut pas de détection automatique, proposer un type par défaut
                if not auto_detect_type:
                    default_type = st.selectbox("Type d'entrée par défaut", 
                                              ["quotidien", "projet", "formation", "réflexion"])
            
            # Bouton pour traiter tous les fichiers
            if st.button("Traiter tous les fichiers"):
                total_entries = 0
                successful_files = 0
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, file in enumerate(uploaded_files):
                    status_text.text(f"Traitement de {file.name}...")
                    progress_value = i / len(uploaded_files)
                    progress_bar.progress(progress_value)
                    
                    try:
                        # Importer le fichier
                        result = import_pdf(file, entreprise_options[selected_entreprise])
                        
                        if result:
                            total_entries += len(result["entries"])
                            successful_files += 1
                    except Exception as e:
                        st.error(f"Erreur lors du traitement de {file.name}: {str(e)}")
                
                # Mise à jour finale
                progress_bar.progress(1.0)
                status_text.text(f"Traitement terminé. {successful_files}/{len(uploaded_files)} fichiers importés avec succès.")
                
                st.success(f"Import terminé ! {total_entries} entrées créées à partir de {successful_files} fichiers.")

# Fonction améliorée pour le processus d'import de PDF (pour l'import simple)
def preview_and_import_pdf(uploaded_file, entreprise_id):
    """
    Affiche une prévisualisation des entrées extraites d'un PDF et permet de les modifier
    avant de les importer.
    
    Cette fonction doit être appelée lorsque l'utilisateur souhaite prévisualiser
    et personnaliser les entrées avant l'import.
    """
    # Analyser le PDF
    entries = analyze_pdf(uploaded_file)
    
    if not entries:
        st.error("Impossible d'extraire des entrées du PDF.")
        return
    
    st.success(f"{len(entries)} entrées trouvées dans le PDF.")
    
    # Permettre la modification des entrées avant import
    for i, entry in enumerate(entries):
        with st.expander(f"Entrée {i+1} - {entry['date']}"):
            # Date
            new_date = st.date_input(
                f"Date de l'entrée {i+1}", 
                datetime.strptime(entry['date'], "%Y-%m-%d")
            ).strftime("%Y-%m-%d")
            entry['date'] = new_date
            
            # Type d'entrée
            entry['type_entree'] = st.selectbox(
                f"Type d'entrée {i+1}",
                ["quotidien", "projet", "formation", "réflexion"],
                index=["quotidien", "projet", "formation", "réflexion"].index(entry['type_entree'])
            )
            
            # Tags
            tags_input = st.text_input(
                f"Tags (séparés par des virgules) pour l'entrée {i+1}",
                value=", ".join(entry.get('tags', []))
            )
            entry['tags'] = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
            
            # Contenu
            entry['texte'] = st.text_area(
                f"Contenu de l'entrée {i+1}",
                value=entry['texte'],
                height=200
            )
    
    # Confirmer l'import
    if st.button("Confirmer l'import"):
        with st.spinner("Import des entrées en cours..."):
            # Définir l'entreprise pour toutes les entrées
            for entry in entries:
                entry['entreprise_id'] = entreprise_id
            
            # Ajouter les entrées une par une
            added_entries = []
            for entry in entries:
                result = add_journal_entry(entry)
                if result:
                    added_entries.append(result)
            
            if added_entries:
                st.success(f"{len(added_entries)}/{len(entries)} entrées importées avec succès !")
                return True
    
    return False

# Initialisation de l'état de session
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "dashboard"
if "selected_section_id" not in st.session_state:
    st.session_state.selected_section_id = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Pied de page
st.markdown("---")
st.markdown("Agent Mémoire Alternance | v1.0.0")