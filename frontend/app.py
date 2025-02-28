import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import os
import time
import tempfile

# Configuration de l'API
API_URL = "http://backend:8000"

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

# Fonctions d'API
def get_entreprises():
    """Récupère la liste des entreprises depuis l'API"""
    try:
        response = requests.get(f"{API_URL}/entreprises")
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la récupération des entreprises.")
        return []

def get_tags():
    """Récupère la liste des tags depuis l'API"""
    try:
        response = requests.get(f"{API_URL}/tags")
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la récupération des tags.")
        return []

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
    
    try:
        response = requests.get(f"{API_URL}/journal/entries", params=params)
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la récupération des entrées du journal.")
        return []

def add_journal_entry(entry_data):
    """Ajoute une entrée au journal via l'API"""
    try:
        response = requests.post(f"{API_URL}/journal/entries", json=entry_data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'ajout de l'entrée: {str(e)}")
        return None

def update_journal_entry(entry_id, entry_data):
    """Met à jour une entrée du journal via l'API"""
    try:
        response = requests.put(f"{API_URL}/journal/entries/{entry_id}", json=entry_data)
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la mise à jour de l'entrée.")
        return None

def delete_journal_entry(entry_id):
    """Supprime une entrée du journal via l'API"""
    try:
        response = requests.delete(f"{API_URL}/journal/entries/{entry_id}")
        response.raise_for_status()
        return True
    except:
        st.error("Erreur lors de la suppression de l'entrée.")
        return False

def get_memoire_sections(parent_id=None):
    """Récupère les sections du mémoire depuis l'API"""
    params = {}
    if parent_id is not None:
        params["parent_id"] = parent_id
    
    try:
        response = requests.get(f"{API_URL}/memoire/sections", params=params)
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la récupération des sections du mémoire.")
        return []

def get_memoire_section(section_id):
    """Récupère une section spécifique du mémoire depuis l'API"""
    try:
        response = requests.get(f"{API_URL}/memoire/sections/{section_id}")
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la récupération de la section.")
        return None

def add_memoire_section(section_data):
    """Ajoute une section au mémoire via l'API"""
    try:
        response = requests.post(f"{API_URL}/memoire/sections", json=section_data)
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de l'ajout de la section.")
        return None

def update_memoire_section(section_id, section_data):
    """Met à jour une section du mémoire via l'API"""
    try:
        response = requests.put(f"{API_URL}/memoire/sections/{section_id}", json=section_data)
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la mise à jour de la section.")
        return None

def delete_memoire_section(section_id):
    """Supprime une section du mémoire via l'API"""
    try:
        response = requests.delete(f"{API_URL}/memoire/sections/{section_id}")
        response.raise_for_status()
        return True
    except:
        st.error("Erreur lors de la suppression de la section.")
        return False

def generate_plan(prompt):
    """Génère un plan de mémoire via l'API IA"""
    try:
        response = requests.post(f"{API_URL}/ai/generate-plan", json={"prompt": prompt})
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la génération du plan.")
        return None

def generate_content(section_id, prompt=None):
    """Génère du contenu pour une section du mémoire via l'API IA"""
    data = {"section_id": section_id}
    if prompt:
        data["prompt"] = prompt
    
    try:
        response = requests.post(f"{API_URL}/ai/generate-content", json=data)
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la génération du contenu.")
        return None

def improve_text(texte, mode):
    """Améliore un texte via l'API IA"""
    try:
        response = requests.post(f"{API_URL}/ai/improve-text", json={"texte": texte, "mode": mode})
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de l'amélioration du texte.")
        return None

def search_entries(query):
    """Recherche des entrées de journal via l'API"""
    try:
        response = requests.get(f"{API_URL}/search", params={"query": query})
        response.raise_for_status()
        return response.json()
    except:
        st.error("Erreur lors de la recherche.")
        return []

# Fonctions pour l'import de PDF
def process_pdf(uploaded_file, entreprise_id, type_entree):
    """Traite un fichier PDF importé et extrait les entrées de journal"""
    try:
        # Enregistrer temporairement le fichier
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            pdf_path = tmp_file.name
        
        # Ici, vous devriez utiliser une bibliothèque comme PyPDF2 ou pdfminer
        # pour extraire le texte du PDF. Pour l'exemple, nous utilisons une
        # extraction simulée.
        
        # Extraction simulée - à remplacer par une extraction réelle
        content = "Contenu extrait du PDF: " + uploaded_file.name
        
        # Créer une entrée de journal
        today = datetime.now().strftime("%Y-%m-%d")
        entry_data = {
            "date": today,
            "texte": content,
            "entreprise_id": entreprise_id,
            "type_entree": type_entree,
            "source_document": uploaded_file.name
        }
        
        # Ajouter l'entrée via l'API
        result = add_journal_entry(entry_data)
        
        # Nettoyer le fichier temporaire
        os.unlink(pdf_path)
        
        return result
    except Exception as e:
        st.error(f"Erreur lors du traitement du PDF: {str(e)}")
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
            
            entreprise = st.selectbox("Entreprise", list(entreprise_options.keys()), index=list(entreprise_options.keys()).index(default_entreprise) if default_entreprise else 0)
            
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
    
    # Onglet Consulter les entrées
    with tab2:
        st.markdown("<h2 class='section-title'>Entrées du journal</h2>", unsafe_allow_html=True)
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_start_date = st.date_input("Date de début", datetime.now() - timedelta(days=30))
        
        with col2:
            filter_end_date = st.date_input("Date de fin", datetime.now())
        
        entreprises = get_entreprises()
        entreprise_options = {e["nom"]: e["id"] for e in entreprises}
        entreprise_options["Toutes"] = None
        
        with col3:
            filter_entreprise = st.selectbox("Entreprise", list(entreprise_options.keys()))
        
        col1, col2 = st.columns(2)
        
        with col1:
            filter_type = st.selectbox("Type d'entrée", ["Tous", "quotidien", "projet", "formation", "réflexion"])
        
        all_tags = get_tags()
        tag_options = ["Tous"] + [tag["nom"] for tag in all_tags]
        
        with col2:
            filter_tag = st.selectbox("Tag", tag_options)
        
        # Récupérer les entrées filtrées
        entries = get_journal_entries(
            start_date=filter_start_date.strftime("%Y-%m-%d"),
            end_date=filter_end_date.strftime("%Y-%m-%d"),
            entreprise_id=entreprise_options[filter_entreprise],
            type_entree=None if filter_type == "Tous" else filter_type,
            tag=None if filter_tag == "Tous" else filter_tag
        )
        
        # Afficher les entrées
        for entry in entries:
            with st.expander(f"{entry['date']} - {entry.get('entreprise_nom', 'Entreprise inconnue')}"):
                # Afficher les tags
                tags_html = ""
                for tag in entry.get("tags", []):
                    tags_html += f"<span class='tag'>{tag}</span>"
                
                st.markdown(tags_html, unsafe_allow_html=True)
                
                # Type d'entrée
                st.write(f"Type: {entry['type_entree']}")
                
                # Contenu
                st.write(entry["texte"])
                
                # Actions
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button(f"Modifier #{entry['id']}", key=f"edit_{entry['id']}"):
                        st.session_state["edit_entry"] = entry
                        st.experimental_rerun()
                
                with col2:
                    if st.button(f"Supprimer #{entry['id']}", key=f"delete_{entry['id']}"):
                        if delete_journal_entry(entry["id"]):
                            st.success("Entrée supprimée avec succès!")
                            st.experimental_rerun()
        
        # Formulaire de modification
        if "edit_entry" in st.session_state:
            entry = st.session_state["edit_entry"]
            
            st.markdown("<h3 class='subsection-title'>Modifier l'entrée</h3>", unsafe_allow_html=True)
            
            with st.form("edit_journal_entry_form"):
                edit_date = st.date_input("Date", datetime.strptime(entry["date"], "%Y-%m-%d"))
                
                # Entreprises
                entreprises = get_entreprises()
                entreprise_options = {e["nom"]: e["id"] for e in entreprises}
                default_entreprise_index = 0
                
                for i, (name, id) in enumerate(entreprise_options.items()):
                    if id == entry["entreprise_id"]:
                        default_entreprise_index = i
                        break
                
                edit_entreprise = st.selectbox("Entreprise", list(entreprise_options.keys()), index=default_entreprise_index)
                
                edit_type_entree = st.selectbox("Type d'entrée", ["quotidien", "projet", "formation", "réflexion"], index=["quotidien", "projet", "formation", "réflexion"].index(entry["type_entree"]))
                
                edit_texte = st.text_area("Contenu", entry["texte"], height=300)
                
                # Tags existants
                all_tags = get_tags()
                existing_tags = [tag["nom"] for tag in all_tags]
                
                # Option pour des tags existants ou nouveaux
                use_existing_tags = st.checkbox("Utiliser des tags existants", value=True)
                
                if use_existing_tags and existing_tags:
                    edit_selected_tags = st.multiselect("Tags", existing_tags, default=entry.get("tags", []))
                else:
                    tags_input = st.text_input("Tags (séparés par des virgules)", ", ".join(entry.get("tags", [])))
                    edit_selected_tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []
                
                submit_edit = st.form_submit_button("Enregistrer les modifications")
                
                if submit_edit:
                    if not edit_texte:
                        st.error("Le contenu ne peut pas être vide.")
                    else:
                        # Préparer les données
                        update_data = {
                            "date": edit_date.strftime("%Y-%m-%d"),
                            "texte": edit_texte,
                            "entreprise_id": entreprise_options[edit_entreprise],
                            "type_entree": edit_type_entree,
                            "tags": edit_selected_tags if edit_selected_tags and edit_selected_tags[0] else None
                        }
                        
                        # Mettre à jour l'entrée
                        result = update_journal_entry(entry["id"], update_data)
                        
                        if result:
                            st.success("Entrée mise à jour avec succès!")
                            # Supprimer l'entrée de la session state
                            del st.session_state["edit_entry"]
                            st.experimental_rerun()
            
            # Bouton pour annuler la modification
            if st.button("Annuler"):
                del st.session_state["edit_entry"]
                st.experimental_rerun()
    
    # Onglet Recherche
    with tab3:
        st.markdown("<h2 class='section-title'>Recherche</h2>", unsafe_allow_html=True)
        
        search_query = st.text_input("Rechercher dans le journal", "")
        
        if search_query:
            results = search_entries(search_query)
            
            st.markdown(f"<p>{len(results)} résultats trouvés</p>", unsafe_allow_html=True)
            
            for result in results:
                similarity = result.get("similarity", 0)
                similarity_percentage = f"{(1 - similarity) * 100:.1f}%" if similarity is not None else "N/A"
                
                st.markdown(f"<div class='entry-container'>", unsafe_allow_html=True)
                st.markdown(f"<p class='entry-date'>{result['date']} - Pertinence: {similarity_percentage}</p>", unsafe_allow_html=True)
                
                # Afficher les tags
                tags_html = ""
                for tag in result.get("tags", []):
                    tags_html += f"<span class='tag'>{tag}</span>"
                
                st.markdown(tags_html, unsafe_allow_html=True)
                
                # Afficher un extrait du texte
                text_preview = result["texte"][:200] + "..." if len(result["texte"]) > 200 else result["texte"]
                st.write(text_preview)
                
                # Lien vers l'entrée complète
                if st.button(f"Voir l'entrée complète #{result['id']}", key=f"view_{result['id']}"):
                    st.session_state["view_entry"] = result["id"]
                    st.experimental_rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        # Afficher l'entrée complète
        if "view_entry" in st.session_state:
            entry_id = st.session_state["view_entry"]
            
            # Récupérer l'entrée
            response = requests.get(f"{API_URL}/journal/entries/{entry_id}")
            if response.status_code == 200:
                entry = response.json()
                
                st.markdown("<h3 class='subsection-title'>Entrée complète</h3>", unsafe_allow_html=True)
                
                st.markdown(f"<p class='entry-date'>{entry['date']} - {entry.get('entreprise_nom', 'Entreprise inconnue')}</p>", unsafe_allow_html=True)
                
                # Afficher les tags
                tags_html = ""
                for tag in entry.get("tags", []):
                    tags_html += f"<span class='tag'>{tag}</span>"
                
                st.markdown(tags_html, unsafe_allow_html=True)
                
                # Type d'entrée
                st.write(f"Type: {entry['type_entree']}")
                
                # Contenu
                st.write(entry["texte"])
                
                # Bouton pour fermer
                if st.button("Fermer"):
                    del st.session_state["view_entry"]
                    st.experimental_rerun()

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
                # response = requests.post(f"{API_URL}/ai/chat", json={"prompt": prompt, "history": st.session_state.messages})
                # answer = response.json()["response"]
                
                # Simulation de réponse
                time.sleep(1)
                answer = f"Je vais vous aider avec votre question sur '{prompt}'.\n\nPour rédiger un bon mémoire d'alternance, il est important de structurer votre pensée et de s'appuyer sur votre expérience professionnelle."
                
                st.markdown(answer)
        
        # Ajouter la réponse de l'assistant à l'historique
        st.session_state.messages.append({"role": "assistant", "content": answer})

elif page == "Import PDF":
    st.markdown("<h1 class='main-title'>Import de documents</h1>", unsafe_allow_html=True)
    
    st.markdown("<h2 class='section-title'>Importer un PDF</h2>", unsafe_allow_html=True)
    
    # Interface d'upload
    uploaded_file = st.file_uploader("Choisissez un fichier PDF", type="pdf")
    
    if uploaded_file:
        # Afficher les informations sur le fichier
        st.write(f"Nom du fichier: {uploaded_file.name}")
        st.write(f"Taille: {uploaded_file.size / 1024:.2f} KB")
        
        # Options d'import
        entreprises = get_entreprises()
        entreprise_options = {e["nom"]: e["id"] for e in entreprises}
        
        selected_entreprise = st.selectbox("Entreprise associée", list(entreprise_options.keys()))
        
        type_entree = st.selectbox("Type d'entrée", ["quotidien", "projet", "formation", "réflexion"])
        
        # Bouton pour traiter le PDF
        if st.button("Importer"):
            with st.spinner("Traitement du PDF en cours..."):
                result = process_pdf(uploaded_file, entreprise_options[selected_entreprise], type_entree)
                
                if result:
                    st.success("PDF importé avec succès!")
                    st.json(result)
