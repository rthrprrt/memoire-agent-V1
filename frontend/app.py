# app.py - Interface Streamlit
import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import websocket
import threading
import time

# Configuration
API_URL = "http://backend:8000"
WS_URL = "ws://backend:8000/ws"

# Configuration de la page
st.set_page_config(
    page_title="Assistant de Rédaction de Mémoire",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Fonctions utilitaires pour l'API
def get_outline():
    """Récupère la structure du plan du mémoire"""
    try:
        response = requests.get(f"{API_URL}/api/outline")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la récupération du plan: {str(e)}")
        return []

def get_section(section_id):
    """Récupère une section par son ID"""
    try:
        response = requests.get(f"{API_URL}/api/section/{section_id}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la récupération de la section: {str(e)}")
        return None

def update_section(section):
    """Met à jour une section"""
    try:
        response = requests.put(f"{API_URL}/api/section/{section['id']}", json=section)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour de la section: {str(e)}")
        return None

def generate_section_content(section_id, prompt=None):
    """Génère du contenu pour une section"""
    try:
        payload = {"section_id": section_id}
        if prompt:
            payload["prompt"] = prompt
        
        response = requests.post(f"{API_URL}/api/section/{section_id}/generate", json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la génération du contenu: {str(e)}")
        return None

def improve_section(section_id, improvement_type):
    """Améliore le contenu d'une section"""
    try:
        payload = {"improvement_type": improvement_type}
        response = requests.post(f"{API_URL}/api/section/{section_id}/improve", json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'amélioration du contenu: {str(e)}")
        return None

def get_journal_entries(limit=50, skip=0):
    """Récupère les entrées du journal de bord"""
    try:
        response = requests.get(f"{API_URL}/api/journal?limit={limit}&skip={skip}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la récupération du journal: {str(e)}")
        return []

def add_journal_entry(entry):
    """Ajoute une entrée au journal de bord"""
    try:
        response = requests.post(f"{API_URL}/api/journal", json=entry)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de l'ajout de l'entrée au journal: {str(e)}")
        return None

def chat_with_assistant(message):
    """Envoie un message à l'assistant"""
    try:
        payload = {
            "content": message,
            "relevant_journal": True,
            "relevant_sections": True
        }
        response = requests.post(f"{API_URL}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la communication avec l'assistant: {str(e)}")
        return {"response": "Désolé, je ne peux pas répondre pour le moment.", "context": {}}

def create_initial_outline():
    """Crée un plan initial pour le mémoire"""
    try:
        response = requests.post(f"{API_URL}/api/outline")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erreur lors de la création du plan: {str(e)}")
        return []

# Fonction pour formater l'affichage du plan
def display_outline(outline, level=0):
    """Affiche le plan du mémoire de manière récursive"""
    if not outline:
        return
    
    for section in outline:
        # Créer l'indentation selon le niveau
        indent = "  " * level
        prefix = "📄 " if level > 0 else "📑 "
        
        # Créer un bouton cliquable pour chaque section
        if st.button(f"{indent}{prefix}{section['title']}", key=f"outline_btn_{section['id']}"):
            st.session_state.selected_section_id = section['id']
            st.session_state.active_tab = "editor"
            st.experimental_rerun()
        
        # Afficher les enfants récursivement
        if "children" in section and section["children"]:
            display_outline(section["children"], level + 1)

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
        color: #1E88E5;
    }
    .section-header {
        font-size: 1.8rem;
        font-weight: bold;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        color: #0D47A1;
    }
    .subsection-header {
        font-size: 1.4rem;
        font-weight: bold;
        margin-top: 0.8rem;
        color: #1565C0;
    }
    .highlight-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #E3F2FD;
        border-left: 5px solid #1E88E5;
        margin-bottom: 1rem;
    }
    .chat-box {
        max-height: 400px;
        overflow-y: auto;
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #F5F5F5;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #E3F2FD;
        padding: 0.5rem 1rem;
        border-radius: 1rem 1rem 0 1rem;
        margin-bottom: 0.5rem;
        display: inline-block;
        max-width: 80%;
    }
    .assistant-message {
        background-color: #F1F8E9;
        padding: 0.5rem 1rem;
        border-radius: 1rem 1rem 1rem 0;
        margin-bottom: 0.5rem;
        display: inline-block;
        max-width: 80%;
    }
    .journal-entry {
        padding: 0.8rem;
        border-radius: 0.3rem;
        background-color: #FFF8E1;
        border-left: 3px solid #FFA000;
        margin-bottom: 0.8rem;
    }
    .progress-container {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .version-box {
        padding: 0.5rem;
        border-radius: 0.3rem;
        background-color: #E8EAF6;
        border-left: 3px solid #3F51B5;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation de l'état de session
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "dashboard"
if "selected_section_id" not in st.session_state:
    st.session_state.selected_section_id = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "websocket" not in st.session_state:
    st.session_state.websocket = None
if "outline_exists" not in st.session_state:
    # Vérifier si un plan existe déjà
    outline = get_outline()
    st.session_state.outline_exists = len(outline) > 0

# Barre de navigation latérale
st.sidebar.markdown('<p class="main-header">📝 Assistant Mémoire</p>', unsafe_allow_html=True)

# Menu de navigation
menu = st.sidebar.radio(
    "Navigation",
    ["Tableau de bord", "Éditeur", "Journal de bord", "Chat avec l'assistant"],
    key="menu",
    index=["dashboard", "editor", "journal", "chat"].index(st.session_state.active_tab)
        if st.session_state.active_tab in ["dashboard", "editor", "journal", "chat"] else 0
)

# Mettre à jour l'onglet actif en fonction du menu
st.session_state.active_tab = {
    "Tableau de bord": "dashboard",
    "Éditeur": "editor",
    "Journal de bord": "journal",
    "Chat avec l'assistant": "chat"
}[menu]

# Section Plan du mémoire dans la barre latérale
with st.sidebar.expander("Plan du mémoire", expanded=True):
    outline = get_outline()
    if outline:
        # Afficher le plan
        for section in outline:
            if st.sidebar.button(f"📑 {section['title']}", key=f"sidebar_section_{section['id']}"):
                st.session_state.selected_section_id = section['id']
                st.session_state.active_tab = "editor"
                st.experimental_rerun()
            
            # Afficher les sous-sections
            if "children" in section and section["children"]:
                for child in section["children"]:
                    if st.sidebar.button(f"  ↳ {child['title']}", key=f"sidebar_child_{child['id']}"):
                        st.session_state.selected_section_id = child['id']
                        st.session_state.active_tab = "editor"
                        st.experimental_rerun()
    else:
        st.sidebar.warning("Aucun plan disponible. Créez-en un depuis le tableau de bord.")

# Contenu principal en fonction de l'onglet actif
if st.session_state.active_tab == "dashboard":
    st.markdown('<p class="main-header">Tableau de Bord</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<p class="section-header">Plan du mémoire</p>', unsafe_allow_html=True)
        
        if not st.session_state.outline_exists:
            st.info("Aucun plan n'a été créé pour le moment.")
            if st.button("Générer un plan initial", key="generate_initial_outline"):
                with st.spinner("Génération du plan en cours..."):
                    outline = create_initial_outline()
                    if outline:
                        st.session_state.outline_exists = True
                        st.success("Plan généré avec succès!")
                        st.experimental_rerun()
        else:
            # Afficher le plan actuel
            if outline:
                for section in outline:
                    st.markdown(f"**{section['title']}**")
                    
                    # Afficher les sous-sections
                    if "children" in section and section["children"]:
                        for child in section["children"]:
                            st.markdown(f"  • {child['title']}")
            
            if st.button("Régénérer le plan", key="regenerate_outline"):
                if st.checkbox("Je confirme vouloir régénérer le plan (cette action ne peut pas être annulée)"):
                    with st.spinner("Régénération du plan en cours..."):
                        outline = create_initial_outline()
                        if outline:
                            st.success("Plan régénéré avec succès!")
                            st.experimental_rerun()
    
    with col2:
        st.markdown('<p class="section-header">Journal de bord</p>', unsafe_allow_html=True)
        
        # Afficher les dernières entrées du journal
        journal_entries = get_journal_entries(limit=5)
        
        if journal_entries:
            for entry in journal_entries:
                with st.expander(f"{entry['date']} - {entry['tags'][0] if entry['tags'] else 'Sans tag'}"):
                    st.markdown(entry['content'][:200] + "..." if len(entry['content']) > 200 else entry['content'])
        else:
            st.info("Aucune entrée de journal trouvée. Ajoutez-en depuis l'onglet Journal de bord.")
        
        # Raccourci pour ajouter une entrée
        if st.button("Ajouter une entrée au journal", key="dashboard_add_journal"):
            st.session_state.active_tab = "journal"
            st.experimental_rerun()
    
    # Statistiques de progression
    st.markdown('<p class="section-header">Progression du mémoire</p>', unsafe_allow_html=True)
    
    # Calculer les statistiques
    if outline:
        total_sections = 0
        sections_with_content = 0
        total_words = 0
        
        # Fonction récursive pour compter les sections
        def count_sections(sections, ts=0, swc=0, tw=0):
            for section in sections:
                ts += 1
                
                # Vérifier si la section a du contenu
                section_data = get_section(section["id"])
                if section_data and section_data["content"] and len(section_data["content"]) > 50:  # Minimum 50 caractères
                    swc += 1
                    tw += len(section_data["content"].split())
                
                # Traiter les enfants
                if "children" in section and section["children"]:
                    new_ts, new_swc, new_tw = count_sections(section["children"], 0, 0, 0)
                    ts += new_ts
                    swc += new_swc
                    tw += new_tw
                    
            return ts, swc, tw

        # Puis appeler la fonction et récupérer les résultats
        total_sections, sections_with_content, total_words = count_sections(outline)
        
        # Calculer les statistiques
        count_sections(outline)
        
        # Afficher les statistiques
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Sections complétées", f"{sections_with_content}/{total_sections}", 
                     f"{int(sections_with_content/total_sections*100)}%" if total_sections > 0 else "0%")
        
        with col2:
            st.metric("Mots rédigés", f"{total_words}", 
                     "sur ~10000 requis" if total_words < 10000 else "✓ Minimum atteint")
        
        with col3:
            # Estimer le temps restant
            if total_sections > sections_with_content:
                remaining_sections = total_sections - sections_with_content
                st.metric("Temps estimé restant", f"{remaining_sections} jours", 
                         "à raison d'une section par jour")
            else:
                st.metric("Temps estimé restant", "0 jours", "Toutes les sections ont du contenu")
        
        # Barre de progression
        progress = sections_with_content / total_sections if total_sections > 0 else 0
        st.progress(progress)
        st.markdown(f"**Progression globale:** {int(progress*100)}%")
    else:
        st.info("Générez d'abord un plan pour voir les statistiques de progression.")
    
    # Suggestions
    st.markdown('<p class="section-header">Suggestions</p>', unsafe_allow_html=True)
    
    if outline:
        # Trouver la prochaine section à rédiger
        next_section = None
        
        def find_next_empty_section(sections):
            for section in sections:
                section_data = get_section(section["id"])
                if section_data and (not section_data["content"] or len(section_data["content"]) < 50):
                    return section
                
                # Vérifier les enfants
                if "children" in section and section["children"]:
                    child_result = find_next_empty_section(section["children"])
                    if child_result:
                        return child_result
            
            return None
        
        next_section = find_next_empty_section(outline)
        
        if next_section:
            st.markdown('<div class="highlight-box">', unsafe_allow_html=True)
            st.markdown(f"**Suggestion:** Rédiger la section **{next_section['title']}**")
            if st.button("Travailler sur cette section", key="work_on_suggested_section"):
                st.session_state.selected_section_id = next_section["id"]
                st.session_state.active_tab = "editor"
                st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.success("Toutes les sections ont du contenu! Vous pouvez maintenant les améliorer.")

elif st.session_state.active_tab == "editor":
    st.markdown('<p class="main-header">Éditeur de Mémoire</p>', unsafe_allow_html=True)
    
    if not st.session_state.selected_section_id:
        st.info("Veuillez sélectionner une section à éditer depuis le plan du mémoire.")
    else:
        # Récupérer les informations de la section
        section = get_section(st.session_state.selected_section_id)
        
        if section:
            # Entête avec titre de la section
            st.markdown(f'<p class="section-header">{section["title"]}</p>', unsafe_allow_html=True)
            
            # Afficher le contenu actuel dans un éditeur de texte
            new_content = st.text_area(
                "Contenu de la section",
                value=section["content"],
                height=400,
                key="section_content_editor"
            )
            
            # Fonctionnalités d'édition
            col1, col2 = st.columns(2)
            
            with col1:
                # Bouton de sauvegarde
                if st.button("Sauvegarder les modifications", key="save_section"):
                    if new_content != section["content"]:
                        section["content"] = new_content
                        section["last_modified"] = datetime.now().isoformat()
                        updated_section = update_section(section)
                        if updated_section:
                            st.success("Section mise à jour avec succès!")
                            # Mettre à jour la section dans l'état
                            section = updated_section
            
            with col2:
                # Génération de contenu
                if st.button("Générer du contenu", key="generate_content"):
                    prompt = st.text_input("Instructions spécifiques (facultatif)", key="generation_prompt")
                    if st.button("Confirmer la génération", key="confirm_generation"):
                        with st.spinner("Génération du contenu en cours..."):
                            updated_section = generate_section_content(section["id"], prompt)
                            if updated_section:
                                st.success("Contenu généré avec succès!")
                                # Mettre à jour la section dans l'état et dans l'éditeur
                                section = updated_section
                                st.experimental_rerun()
            
            # Outils d'amélioration
            st.markdown('<p class="subsection-header">Outils d\'amélioration</p>', unsafe_allow_html=True)
            
            improvement_type = st.selectbox(
                "Type d'amélioration",
                options=["style", "grammar", "structure", "depth", "concision"],
                format_func=lambda x: {
                    "style": "Améliorer le style d'écriture",
                    "grammar": "Corriger la grammaire et l'orthographe",
                    "structure": "Améliorer la structure et l'organisation",
                    "depth": "Approfondir l'analyse",
                    "concision": "Rendre le texte plus concis"
                }[x],
                key="improvement_type"
            )
            
            if st.button("Appliquer l'amélioration", key="apply_improvement"):
                with st.spinner(f"Amélioration du texte en cours ({improvement_type})..."):
                    updated_section = improve_section(section["id"], improvement_type)
                    if updated_section:
                        st.success("Texte amélioré avec succès!")
                        # Mettre à jour la section dans l'état
                        section = updated_section
                        st.experimental_rerun()
            
            # Entrées de journal pertinentes
            st.markdown('<p class="subsection-header">Entrées de journal pertinentes</p>', unsafe_allow_html=True)
            
            # Rechercher des entrées pertinentes
            journal_entries = get_journal_entries(limit=100)
            
            # Filtrer les entrées pertinentes (simulation - dans un cas réel, utilisez l'API)
            # Recherche simple basée sur les mots-clés du titre
            keywords = section["title"].lower().split()
            relevant_entries = []
            
            for entry in journal_entries:
                relevance_score = 0
                content_lower = entry["content"].lower()
                
                for keyword in keywords:
                    if keyword in content_lower and len(keyword) > 3:  # Ignorer les mots courts
                        relevance_score += 1
                
                if relevance_score > 0:
                    relevant_entries.append({
                        **entry,
                        "relevance_score": relevance_score
                    })
            
            # Trier par pertinence
            relevant_entries.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            if relevant_entries:
                for entry in relevant_entries[:3]:  # Afficher les 3 plus pertinentes
                    with st.expander(f"{entry['date']} - Score: {entry['relevance_score']}"):
                        st.markdown(f"**Tags:** {', '.join(entry['tags']) if entry['tags'] else 'Aucun tag'}")
                        st.markdown(entry["content"])
                        
                        # Bouton pour insérer le contenu
                        if st.button("Utiliser cette entrée", key=f"use_entry_{entry['id']}"):
                            # Ajouter le contenu à la fin de la section
                            new_content = section["content"] + "\n\n" + entry["content"]
                            section["content"] = new_content
                            updated_section = update_section(section)
                            if updated_section:
                                st.success("Contenu de l'entrée ajouté à la section!")
                                section = updated_section
                                st.experimental_rerun()
            else:
                st.info("Aucune entrée de journal pertinente trouvée.")

elif st.session_state.active_tab == "journal":
    st.markdown('<p class="main-header">Journal de Bord</p>', unsafe_allow_html=True)
    
    # Interface pour ajouter une nouvelle entrée
    with st.expander("Ajouter une nouvelle entrée", expanded=True):
        date = st.date_input("Date", value=datetime.now().date())
        tags = st.multiselect("Tags", options=["Réunion", "Développement", "Formation", "Projet", "Autre"])
        content = st.text_area("Contenu de l'entrée", height=200)
        
        if st.button("Ajouter l'entrée", key="add_journal_entry"):
            if content:
                # Formater l'entrée
                entry = {
                    "date": date.isoformat(),
                    "content": content,
                    "tags": tags
                }
                
                # Ajouter l'entrée
                result = add_journal_entry(entry)
                if result:
                    st.success("Entrée ajoutée avec succès!")
                    st.experimental_rerun()
            else:
                st.error("Le contenu de l'entrée ne peut pas être vide.")
    
    # Afficher les entrées existantes
    st.markdown('<p class="section-header">Entrées existantes</p>', unsafe_allow_html=True)
    
    # Options de filtrage
    col1, col2 = st.columns(2)
    
    with col1:
        filter_tag = st.multiselect("Filtrer par tag", options=["Réunion", "Développement", "Formation", "Projet", "Autre"])
    
    with col2:
        sort_order = st.radio("Ordre de tri", options=["Plus récent d'abord", "Plus ancien d'abord"])
    
    # Récupérer les entrées
    journal_entries = get_journal_entries(limit=100)
    
    # Appliquer le filtrage
    if filter_tag:
        journal_entries = [entry for entry in journal_entries if any(tag in entry["tags"] for tag in filter_tag)]
    
    # Appliquer le tri
    if sort_order == "Plus ancien d'abord":
        journal_entries.sort(key=lambda x: x["date"])
    else:
        journal_entries.sort(key=lambda x: x["date"], reverse=True)
    
    # Afficher les entrées
    if journal_entries:
        for entry in journal_entries:
            with st.expander(f"{entry['date']} - {', '.join(entry['tags']) if entry['tags'] else 'Sans tag'}"):
                st.markdown(entry["content"])
                
                # Options pour utiliser cette entrée
                if st.button("Utiliser dans le mémoire", key=f"use_in_memoir_{entry['id']}"):
                    # Afficher les sections disponibles
                    outline = get_outline()
                    
                    if outline:
                        st.selectbox(
                            "Sélectionner une section",
                            options=[section["id"] for section in outline],
                            format_func=lambda x: next((s["title"] for s in outline if s["id"] == x), x),
                            key=f"section_select_{entry['id']}"
                        )
                        
                        if st.button("Confirmer", key=f"confirm_use_{entry['id']}"):
                            selected_section_id = st.session_state[f"section_select_{entry['id']}"]
                            st.session_state.selected_section_id = selected_section_id
                            st.session_state.active_tab = "editor"
                            st.experimental_rerun()
    else:
        st.info("Aucune entrée de journal trouvée.")

elif st.session_state.active_tab == "chat":
    st.markdown('<p class="main-header">Chat avec l\'Assistant</p>', unsafe_allow_html=True)
    
    # Afficher l'historique des messages
    st.markdown('<div class="chat-box">', unsafe_allow_html=True)
    
    for message in st.session_state.chat_messages:
        if message["role"] == "user":
            st.markdown(f'<div class="user-message">{message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="assistant-message">{message["content"]}</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Zone de saisie pour le nouveau message
    user_message = st.text_input("Votre message", key="user_message")
    
    if st.button("Envoyer", key="send_message") or (user_message and user_message != st.session_state.get("last_message", "")):
        if user_message:
            # Ajouter le message de l'utilisateur à l'historique
            st.session_state.chat_messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Sauvegarder le dernier message pour éviter les duplications
            st.session_state.last_message = user_message
            
            # Envoyer le message à l'assistant
            with st.spinner("L'assistant réfléchit..."):
                response = chat_with_assistant(user_message)
                
                # Ajouter la réponse de l'assistant à l'historique
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": response["response"]
                })
            
            # Réinitialiser le champ de saisie
            st.experimental_rerun()
    
    # Options pour le chat
    with st.expander("Options avancées"):
        st.checkbox("Inclure les entrées de journal pertinentes", value=True, key="include_journal")
        st.checkbox("Inclure les sections pertinentes du mémoire", value=True, key="include_sections")
        
        if st.button("Effacer l'historique", key="clear_history"):
            st.session_state.chat_messages = []
            st.success("Historique effacé!")
            st.experimental_rerun()

# Pied de page
st.markdown("---")
st.markdown("Assistant IA de Rédaction de Mémoire | Propulsé par des modèles open source via Ollama")

# Lancer l'application
if __name__ == "__main__":
    st.write("Application démarrée!")
