"""
Module d'extraction de texte à partir de fichiers PDF et DOCX
avec fonctionnalités d'organisation et d'analyse de contenu.
"""

import os
import re
import tempfile
from datetime import datetime, timedelta
from io import BytesIO
import logging
from typing import List, Dict, Any, Optional, Tuple

# Configuration du logging
logger = logging.getLogger(__name__)

# Tentative d'importation de PyPDF2
try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    logger.warning("PyPDF2 n'est pas installé. L'extraction PDF utilisera pdfminer si disponible.")
    PYPDF2_AVAILABLE = False

# Tentative d'importation de pdfminer.six
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    from pdfminer.pdfparser import PDFSyntaxError
    PDFMINER_AVAILABLE = True
except ImportError:
    logger.warning("pdfminer.six n'est pas installé. L'extraction PDF pourrait être limitée.")
    PDFMINER_AVAILABLE = False

# Tentative d'importation de python-docx
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    logger.warning("python-docx n'est pas installé. L'extraction DOCX ne sera pas disponible.")
    DOCX_AVAILABLE = False

def extract_text_from_pdf(pdf_data: bytes) -> Optional[str]:
    """
    Extrait le texte d'un fichier PDF.
    
    Args:
        pdf_data: Les données PDF sous forme de bytes
        
    Returns:
        str: Le texte extrait du document PDF
        None: En cas d'erreur
    """
    # Normaliser l'entrée en BytesIO
    pdf_data_io = BytesIO(pdf_data)
    
    extracted_text = ""
    last_error = None
    
    # Essayer d'abord avec PyPDF2 s'il est disponible
    if PYPDF2_AVAILABLE:
        try:
            reader = PdfReader(pdf_data_io)
            texts = []
            
            for page in reader.pages:
                texts.append(page.extract_text())
            
            extracted_text = "\n\n".join([t for t in texts if t])
            
            # Si l'extraction a réussi, retourner le texte
            if extracted_text.strip():
                return extracted_text
            
            # Sinon, essayer avec pdfminer
            logger.info("PyPDF2 n'a pas pu extraire de texte, essai avec pdfminer...")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Erreur lors de l'extraction avec PyPDF2: {e}")
    
    # Essayer avec pdfminer.six s'il est disponible
    if PDFMINER_AVAILABLE:
        try:
            # pdfminer nécessite un fichier, donc nous devons sauvegarder les données temporairement
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                # Revenir au début du BytesIO
                pdf_data_io.seek(0)
                tmp_file.write(pdf_data_io.read())
                tmp_path = tmp_file.name
            
            try:
                extracted_text = pdfminer_extract_text(tmp_path)
            finally:
                # Nettoyer le fichier temporaire
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            return extracted_text
        
        except PDFSyntaxError as e:
            last_error = f"Erreur de syntaxe PDF: {str(e)}"
            logger.error(f"Erreur de syntaxe PDF: {e}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Erreur lors de l'extraction avec pdfminer: {e}")
    
    # Si aucune méthode n'a fonctionné, retourner None
    if not extracted_text:
        logger.error("Aucune méthode d'extraction n'a pu extraire du texte du PDF")
        if not last_error:
            last_error = "Impossible d'extraire le texte du PDF."
        return None
    
    return extracted_text

def extract_text_from_docx(docx_data: bytes) -> Optional[str]:
    """
    Extrait le texte d'un fichier DOCX.
    
    Args:
        docx_data: Les données DOCX sous forme de bytes
        
    Returns:
        str: Le texte extrait du document DOCX
        None: En cas d'erreur
    """
    if not DOCX_AVAILABLE:
        logger.error("python-docx n'est pas installé, impossible d'extraire le texte du DOCX")
        return None
    
    try:
        # Sauvegarder les données dans un fichier temporaire
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
            tmp_file.write(docx_data)
            tmp_path = tmp_file.name
        
        try:
            # Ouvrir le document avec python-docx
            doc = docx.Document(tmp_path)
            
            # Méthode améliorée pour extraire le texte
            full_text = []
            
            # Extraire le texte de chaque paragraphe
            for para in doc.paragraphs:
                if para.text.strip():  # Ignorer les paragraphes vides
                    full_text.append(para.text.strip())
            
            # Extraire le texte des tableaux
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        full_text.append(" | ".join(row_cells))
            
            # Joindre tous les paragraphes avec des sauts de ligne
            extracted_text = "\n".join(full_text)
            
            # Vérification de sécurité pour garantir un contenu minimal
            if not extracted_text or len(extracted_text) < 10:
                logger.warning(f"Le texte extrait est trop court ({len(extracted_text) if extracted_text else 0} caractères)")
                # Essayer une méthode alternative avec une extraction paragraphe par paragraphe
                alt_text = []
                for para in doc.paragraphs:
                    para_text = para.text
                    logger.info(f"Paragraphe: '{para_text[:50]}...' (longueur: {len(para_text)})")
                    alt_text.append(para_text)
                
                full_alt_text = "\n".join(alt_text)
                if len(full_alt_text) > len(extracted_text):
                    extracted_text = full_alt_text
                    logger.info(f"Méthode alternative a produit un texte plus long: {len(extracted_text)} caractères")
            
            logger.info(f"Texte extrait du DOCX: {len(extracted_text)} caractères")
            logger.info(f"Début du texte: {extracted_text[:100]}...")
            
            return extracted_text
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction du texte du DOCX: {e}")
        return None

def extract_dates_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Recherche et extrait les dates présentes dans le texte avec des informations contextuelles.
    
    Args:
        text: Le texte à analyser
        
    Returns:
        List[Dict]: Liste de dictionnaires contenant:
            - position: position dans le texte
            - date: date au format ISO
            - original: texte original de la date
            - score: score de pertinence (0-100)
            - is_primary: si cette date est susceptible d'être la date principale
            - context: contexte autour de la date
    """
    # Pattern pour les dates au format français et international
    date_patterns = [
        # Format français avec jour de la semaine
        r'(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
        # Format français sans jour de la semaine
        r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
        # Format ISO
        r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
        # Format européen
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
    ]
    
    # Marqueurs temporels relatifs
    relative_time_patterns = [
        # Aujourd'hui, hier, demain, etc.
        r'\b(aujourd\'hui|hier|avant[\s-]hier|demain|après[\s-]demain)\b',
        # La semaine dernière, le mois prochain, etc.
        r'\b(la\s+semaine\s+dernière|la\s+semaine\s+prochaine|le\s+mois\s+dernier|le\s+mois\s+prochain)\b',
        # Jour de la semaine relatif (lundi dernier, etc.)
        r'\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)(\s+dernier|\s+prochain)\b'
    ]
    
    # Dictionnaire de conversion mois français -> numéro
    month_to_number = {
        'janvier': '01', 'février': '02', 'mars': '03', 'avril': '04',
        'mai': '05', 'juin': '06', 'juillet': '07', 'août': '08',
        'septembre': '09', 'octobre': '10', 'novembre': '11', 'décembre': '12'
    }
    
    # Rechercher toutes les occurrences potentielles de dates
    dates_found = []
    
    # Logging pour le debug
    logger.info(f"Texte à analyser pour les dates: {text[:200]}..." if len(text) > 200 else text)
    
    # 1. Extraire les dates absolues
    for pattern in date_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date_str = match.group(0)
            position = match.start()
            
            logger.info(f"Date absolue trouvée: {date_str} à la position {position}")
            
            # Extraire le contexte (30 caractères avant et après la date)
            start_context = max(0, position - 30)
            end_context = min(len(text), position + len(date_str) + 30)
            context = text[start_context:end_context]
            
            # Convertir la date au format ISO (YYYY-MM-DD)
            try:
                # Vérifier si c'est une date en français avec un mois en lettres
                has_month_name = False
                for month_name in month_to_number.keys():
                    if month_name in date_str.lower():
                        has_month_name = True
                        break
                
                if has_month_name:
                    # Format français avec ou sans jour de la semaine
                    parts = date_str.split()
                    
                    # Extraire les composants en fonction du format
                    if parts[0].lower() in ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']:
                        # Avec jour de la semaine
                        day = parts[1]
                        month = parts[2].lower()
                        year = parts[3]
                    else:
                        # Sans jour de la semaine
                        day = parts[0]
                        month = parts[1].lower()
                        year = parts[2]
                    
                    month_num = month_to_number.get(month, '01')
                    iso_date = f"{year}-{month_num}-{day.zfill(2)}"
                elif '-' in date_str or '/' in date_str:
                    # Format ISO ou européen
                    separator = '-' if '-' in date_str else '/'
                    parts = date_str.split(separator)
                    
                    if len(parts[0]) == 4:
                        # Format ISO (YYYY-MM-DD)
                        year = parts[0]
                        month = parts[1].zfill(2)
                        day = parts[2].zfill(2)
                    else:
                        # Format européen (DD-MM-YYYY)
                        day = parts[0].zfill(2)
                        month = parts[1].zfill(2)
                        year = parts[2]
                    
                    iso_date = f"{year}-{month}-{day}"
                else:
                    # Format non reconnu
                    continue
                
                # Vérifier si la date est valide
                datetime.strptime(iso_date, "%Y-%m-%d")
                
                # Analyser le contexte pour déterminer l'importance de cette date
                score, is_primary = analyze_date_context(date_str, context, position)
                
                dates_found.append({
                    "position": position,
                    "date": iso_date,
                    "original": date_str,
                    "score": score,
                    "is_primary": is_primary,
                    "context": context
                })
                
            except ValueError:
                # Date invalide, ignorer
                continue
    
    # 2. Extraire les dates relatives (aujourd'hui, hier, etc.)
    today = datetime.now().date()
    for pattern in relative_time_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            relative_date_str = match.group(0).lower()
            position = match.start()
            
            logger.info(f"Date relative trouvée: {relative_date_str} à la position {position}")
            
            # Extraire le contexte
            start_context = max(0, position - 30)
            end_context = min(len(text), position + len(relative_date_str) + 30)
            context = text[start_context:end_context]
            
            # Convertir la date relative en date absolue
            relative_date = today  # Par défaut
            
            try:
                if 'aujourd\'hui' in relative_date_str:
                    relative_date = today
                elif 'hier' in relative_date_str:
                    relative_date = today - timedelta(days=1)
                elif 'avant-hier' in relative_date_str:
                    relative_date = today - timedelta(days=2)
                elif 'demain' in relative_date_str:
                    relative_date = today + timedelta(days=1)
                elif 'après-demain' in relative_date_str:
                    relative_date = today + timedelta(days=2)
                elif 'semaine dernière' in relative_date_str:
                    relative_date = today - timedelta(days=7)
                elif 'semaine prochaine' in relative_date_str:
                    relative_date = today + timedelta(days=7)
                elif 'mois dernier' in relative_date_str:
                    # Simplification: 30 jours
                    relative_date = today - timedelta(days=30)
                elif 'mois prochain' in relative_date_str:
                    # Simplification: 30 jours
                    relative_date = today + timedelta(days=30)
                elif any(day in relative_date_str for day in ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']):
                    # Traitement des jours de la semaine relatifs
                    day_names = {'lundi': 0, 'mardi': 1, 'mercredi': 2, 'jeudi': 3, 'vendredi': 4, 'samedi': 5, 'dimanche': 6}
                    
                    # Trouver quel jour est mentionné
                    day_name = next(day for day in day_names.keys() if day in relative_date_str)
                    target_weekday = day_names[day_name]
                    
                    # Calculer les jours jusqu'au prochain jour de la semaine spécifié
                    days_ahead = target_weekday - today.weekday()
                    if days_ahead <= 0:  # Target day already happened this week
                        days_ahead += 7
                    
                    if 'dernier' in relative_date_str:
                        # La semaine dernière
                        days_ahead -= 14  # Aller deux semaines en arrière puis avancer
                    
                    relative_date = today + timedelta(days=days_ahead)
                
                # Ajouter cette date avec un score élevé (date relative = haute importance)
                iso_date = relative_date.strftime("%Y-%m-%d")
                score, is_primary = analyze_date_context(relative_date_str, context, position, is_relative=True)
                
                dates_found.append({
                    "position": position,
                    "date": iso_date,
                    "original": relative_date_str,
                    "score": score,
                    "is_primary": is_primary,
                    "context": context
                })
                
            except Exception as e:
                logger.error(f"Erreur lors de la conversion de la date relative: {str(e)}")
                continue
    
    # Trier les dates par score puis par position
    dates_found.sort(key=lambda x: (-x["score"], x["position"]))
    
    # Simplification: si plusieurs dates ont un score élevé (> 70), marquer seulement la première comme primaire
    if dates_found and dates_found[0]["score"] > 70:
        dates_found[0]["is_primary"] = True
        for i in range(1, len(dates_found)):
            dates_found[i]["is_primary"] = False
    
    # Compatibilité avec l'ancienne structure
    date_positions = [(date["position"], date["date"]) for date in dates_found]
    date_positions.sort(key=lambda x: x[0])  # Trier par position
    
    logger.info(f"Dates analysées: {dates_found}")
    return date_positions, dates_found

def analyze_date_context(date_str: str, context: str, position: int, is_relative: bool = False) -> Tuple[int, bool]:
    """
    Analyse le contexte autour d'une date pour déterminer son importance.
    
    Args:
        date_str: Texte de la date
        context: Contexte autour de la date
        position: Position de la date dans le texte
        is_relative: Si la date est relative (aujourd'hui, hier, etc.)
        
    Returns:
        Tuple[int, bool]: (score de pertinence (0-100), si c'est probablement la date principale)
    """
    score = 50  # Score par défaut
    
    # Facteurs qui augmentent l'importance
    importance_indicators = [
        (r'^[^\.]*' + re.escape(date_str), 25),  # Date au début d'une phrase
        (r'^' + re.escape(date_str), 40),  # Date au début du texte
        (r'le ' + re.escape(date_str), 10),  # "Le" avant la date
        (r'date.*?:.*?' + re.escape(date_str), 30),  # Format "Date: ..."
        (r'jour.*?:.*?' + re.escape(date_str), 30),  # Format "Jour: ..."
        (r'\. ' + re.escape(date_str), 20),  # Date juste après un point (début de phrase)
    ]
    
    # Facteurs qui diminuent l'importance (références au passé/futur)
    diminish_indicators = [
        (r'depuis (le|la|les) ' + re.escape(date_str), -20),  # "depuis le..."
        (r'avant (le|la|les) ' + re.escape(date_str), -20),  # "avant le..."
        (r'après (le|la|les) ' + re.escape(date_str), -20),  # "après le..."
        (r'jusqu\'(au|à la) ' + re.escape(date_str), -15),  # "jusqu'au..."
        (r'à partir (du|de la) ' + re.escape(date_str), -15),  # "à partir du..."
        (r'commencé (le|la|en) ' + re.escape(date_str), -10),  # "commencé le..."
        (r'terminé (le|la|en) ' + re.escape(date_str), -10),  # "terminé le..."
    ]
    
    # Analyser les indicateurs
    for pattern, points in importance_indicators:
        if re.search(pattern, context, re.IGNORECASE):
            score += points
    
    for pattern, points in diminish_indicators:
        if re.search(pattern, context, re.IGNORECASE):
            score += points
    
    # Les dates relatives ont généralement plus d'importance
    if is_relative:
        score += 15
    
    # Les dates en début de document ont plus d'importance
    if position < 200:
        score += 20
    
    # Limiter le score entre 0 et 100
    score = max(0, min(100, score))
    
    # Déterminer si c'est probablement la date principale
    is_primary = score > 70
    
    return score, is_primary

def extract_automatic_tags(text: str, threshold: float = 0.01) -> List[str]:
    """
    Extrait automatiquement des tags à partir du texte.
    
    Args:
        text: Le texte à analyser
        threshold: Seuil de fréquence pour considérer un mot comme tag
        
    Returns:
        List[str]: Liste de tags potentiels
    """
    # Extraction des mots (sans ponctuation, chiffres, etc.)
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]{4,}\b', text.lower())
    
    # Filtrer les mots vides (stopwords)
    stopwords = set(['dans', 'avec', 'pour', 'cette', 'mais', 'avoir', 'faire', 
                     'plus', 'tout', 'bien', 'être', 'comme', 'nous', 'leur', 
                     'sans', 'vous', 'dont', 'alors', 'aussi', 'donc', 'cela',
                     'ceux', 'celle', 'celui', 'entre', 'pendant', 'depuis'])
    words = [w for w in words if w not in stopwords]
    
    # Compter les occurrences
    word_counts = {}
    for word in words:
        word_counts[word] = word_counts.get(word, 0) + 1
    
    total_words = len(words)
    if total_words == 0:
        return []
    
    # Sélectionner les mots qui dépassent le seuil
    potential_tags = [word for word, count in word_counts.items() 
                     if count / total_words > threshold and count > 1]
    
    # Limiter le nombre de tags
    return potential_tags[:5]

def analyze_entry_content(text: str) -> Dict[str, Any]:
    """
    Analyse le contenu d'une entrée pour en extraire des informations.
    
    Args:
        text: Le texte à analyser
        
    Returns:
        Dict: Informations extraites (type, entreprise, tags)
    """
    result = {
        "type_entree": "quotidien",  # valeur par défaut
        "entreprise_id": None,
        "tags": extract_automatic_tags(text)
    }
    
    # Détection de type d'entrée
    if re.search(r'\b(formation|cours|apprendre|étudier|apprentissage)\b', text.lower()):
        result["type_entree"] = "formation"
    elif re.search(r'\b(projet|développement|application|implémentation|feature)\b', text.lower()):
        result["type_entree"] = "projet"
    elif re.search(r'\b(réflexion|analyse|pensée|considération|bilan)\b', text.lower()):
        result["type_entree"] = "réflexion"
    
    return result

def process_document(file_content: bytes, filename: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Traite un document (PDF ou DOCX) et extrait son contenu sous forme d'entrées de journal.
    
    Args:
        file_content: Le contenu du fichier
        filename: Le nom du fichier
        
    Returns:
        List[Dict]: Liste des entrées extraites
    """
    # Déterminer le type de fichier et extraire le texte
    if filename and filename.lower().endswith('.pdf'):
        text = extract_text_from_pdf(file_content)
    elif filename and filename.lower().endswith('.docx'):
        text = extract_text_from_docx(file_content)
    else:
        logger.error(f"Type de fichier non pris en charge: {filename}")
        return []
    
    if not text:
        logger.error(f"Impossible d'extraire du texte du document '{filename}'")
        return []
    
    # Rechercher les dates pour diviser le contenu
    date_positions, dates_analyzed = extract_dates_from_text(text)
    
    # Logging pour debug
    logger.info(f"Dates trouvées dans le document: {len(dates_analyzed)} dates")
    
    # Si aucune date n'est trouvée, utiliser la date actuelle
    if not dates_analyzed:
        logger.info("Aucune date trouvée, utilisation de la date actuelle")
        current_date = datetime.now().strftime("%Y-%m-%d")
        metadata = analyze_entry_content(text)
        return [{
            "date": current_date,
            "texte": text,
            "type_entree": metadata["type_entree"],
            "tags": metadata["tags"],
            "source_document": filename
        }]
    
    # Stratégie de traitement des dates:
    # 1. Trouver la date principale (avec le meilleur score)
    # 2. Créer une entrée pour cette date avec le texte complet
    # 3. Si d'autres dates sont pertinentes, créer des entrées séparées
    
    # Identifier la date principale
    primary_dates = [d for d in dates_analyzed if d["is_primary"]]
    if primary_dates:
        primary_date = primary_dates[0]
    else:
        # Si aucune date n'est marquée comme principale, prendre celle avec le score le plus élevé
        primary_date = dates_analyzed[0]  # Déjà triées par score
    
    logger.info(f"Date principale identifiée: {primary_date['date']} (score: {primary_date['score']})")
    
    # Créer une entrée principale avec la date principale et tout le texte
    metadata = analyze_entry_content(text)
    primary_entry = {
        "date": primary_date["date"],
        "texte": text,
        "type_entree": metadata["type_entree"],
        "tags": metadata["tags"],
        "source_document": filename,
        "primary_date": True  # Marquer cette entrée comme utilisant la date principale
    }
    
    # Décider si nous devons créer des entrées séparées pour d'autres dates
    # Stratégie: ne créer des entrées séparées que pour les dates avec un score élevé
    # et qui ne sont pas trop proches de la date principale
    
    secondary_entries = []
    date_diff_threshold = 7  # Différence minimale en jours
    score_threshold = 65    # Score minimum pour les dates secondaires
    
    for date_info in dates_analyzed:
        # Ne pas traiter à nouveau la date principale
        if date_info["date"] == primary_date["date"]:
            continue
        
        # Vérifier si cette date a un score assez élevé
        if date_info["score"] < score_threshold:
            continue
        
        # Calculer la différence en jours entre cette date et la date principale
        try:
            this_date = datetime.strptime(date_info["date"], "%Y-%m-%d").date()
            primary_d = datetime.strptime(primary_date["date"], "%Y-%m-%d").date()
            days_diff = abs((this_date - primary_d).days)
            
            if days_diff < date_diff_threshold:
                # Dates trop proches, ignorer
                continue
                
            # Extraire un contexte significatif autour de cette date
            pos = date_info["position"]
            max_context_length = 1000  # Caractères
            
            # Trouver où commencer la découpe (paragraphe ou phrase)
            context_start = max(0, pos - 100)
            # Reculer jusqu'au début d'une phrase ou d'un paragraphe
            while context_start > 0 and text[context_start] not in ".!?\n":
                context_start -= 1
            if context_start > 0:
                context_start += 1  # Avancer après le marqueur de fin
            
            # Trouver où terminer la découpe
            context_end = min(len(text), pos + 900)
            # Avancer jusqu'à la fin d'une phrase ou d'un paragraphe
            while context_end < len(text) - 1 and text[context_end] not in ".!?\n":
                context_end += 1
            if context_end < len(text) - 1:
                context_end += 1  # Inclure le marqueur de fin
            
            # Extraire le contexte
            context_text = text[context_start:context_end].strip()
            
            # Vérifier si le contexte est suffisamment long
            if len(context_text) >= 10:
                # Créer une entrée secondaire
                secondary_metadata = analyze_entry_content(context_text)
                secondary_entry = {
                    "date": date_info["date"],
                    "texte": context_text,
                    "type_entree": secondary_metadata["type_entree"],
                    "tags": secondary_metadata["tags"],
                    "source_document": filename,
                    "primary_date": False  # Marquer cette entrée comme utilisant une date secondaire
                }
                secondary_entries.append(secondary_entry)
                logger.info(f"Entrée secondaire créée avec date {date_info['date']} (score: {date_info['score']}, contexte: {len(context_text)} caractères)")
        except Exception as e:
            logger.error(f"Erreur lors de la création d'une entrée secondaire: {str(e)}")
    
    # Compiler les entrées (principale + secondaires) selon la stratégie choisie
    entries = [primary_entry]
    
    # Option: ajouter des entrées secondaires (désactivé par défaut)
    include_secondary_entries = False  # Paramètre configurable
    
    if include_secondary_entries and secondary_entries:
        entries.extend(secondary_entries)
    
    return entries

# Garder la fonction existante pour la compatibilité
def process_pdf_file(file_content: bytes, filename: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Traite un fichier PDF et extrait son contenu sous forme d'entrées de journal.
    
    Args:
        file_content: Le contenu du fichier PDF
        filename: Le nom du fichier
        
    Returns:
        List[Dict]: Liste des entrées extraites
    """
    return process_document(file_content, filename)