from fastapi import APIRouter, HTTPException, Depends, Query, Path, Request
from typing import Dict, List, Optional, Any
import logging
import os
import inspect
from datetime import datetime
import json
import sqlite3

from db.database import get_db_connection
from core.exceptions import DatabaseError
from api.models.admin import (
    RouteInfo,
    RouteDetailedInfo,
    RouteParameter,
    SystemInfoResponse,
    DatabaseStructure,
    DatabaseQueryRequest,
    DatabaseQueryResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/system-info", response_model=SystemInfoResponse)
async def get_system_info():
    """
    Récupère des informations système pour le monitoring et le débogage
    
    Cette fonction permet d'obtenir des informations sur l'état du système, comme le nombre d'entrées,
    l'utilisation de mémoire, les versions, etc.
    """
    try:
        # Récupérer les informations sur le système (OS, Python, librairies)
        import sys
        import platform
        import psutil
        
        # Informations générales
        system_info = {
            "datetime": datetime.now().isoformat(),
            "os": platform.platform(),
            "python_version": sys.version,
            "cpu_count": os.cpu_count(),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            },
            "environment": {
                "env_vars": {k: v for k, v in os.environ.items() if k.startswith(("LOG_", "API_", "DB_", "APP_"))}
            }
        }
        
        # Informations sur les packages installés
        import pkg_resources
        installed_packages = [{"name": pkg.key, "version": pkg.version} for pkg in pkg_resources.working_set]
        system_info["installed_packages"] = installed_packages
        
        # Informations sur la base de données
        db_info = {}
        conn = await get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Nombre d'entrées dans la base
            cursor.execute("SELECT COUNT(*) FROM journal_entries")
            db_info["journal_entries_count"] = cursor.fetchone()[0]
            
            # Nombre de sections de mémoire
            cursor.execute("SELECT COUNT(*) FROM memoire_sections")
            db_info["memoire_sections_count"] = cursor.fetchone()[0]
            
            # Nombre d'entreprises
            cursor.execute("SELECT COUNT(*) FROM entreprises")
            db_info["entreprises_count"] = cursor.fetchone()[0]
            
            # Taille de la base de données SQLite
            db_path = os.environ.get("SQLITE_DB_PATH", "data/memoire.db")
            if os.path.exists(db_path):
                db_info["sqlite_file_size"] = os.path.getsize(db_path)
            
            system_info["database"] = db_info
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des informations de la base de données: {str(e)}")
            system_info["database_error"] = str(e)
        finally:
            conn.close()
            
        return system_info
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations système: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/routes", response_model=List[RouteInfo])
async def get_all_routes(request: Request):
    """
    Récupère la liste de toutes les routes API enregistrées
    
    Cette fonction permet d'obtenir des informations sur toutes les routes disponibles,
    utile pour l'auto-documentation et le débogage.
    """
    try:
        routes = []
        for route in request.app.routes:
            route_info = {
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if hasattr(route, "methods") else [],
                "tags": route.tags if hasattr(route, "tags") else []
            }
            routes.append(route_info)
        
        return routes
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des routes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/routes/{path:path}", response_model=RouteDetailedInfo)
async def get_route_details(request: Request, path: str = Path(..., description="Chemin de la route")):
    """
    Récupère les détails d'une route API spécifique
    
    Cette fonction permet d'obtenir des informations détaillées sur une route, y compris
    sa documentation, ses paramètres, son modèle de réponse, etc.
    """
    try:
        # Prétraitement du chemin si nécessaire
        if path.startswith("/"):
            path = path[1:]
        
        # Trouver la route correspondante
        target_route = None
        for route in request.app.routes:
            # Comparer le chemin de manière flexible
            route_path = route.path.lstrip("/")
            if route_path == path:
                target_route = route
                break
        
        if not target_route:
            raise HTTPException(status_code=404, detail=f"Route {path} non trouvée")
        
        # Récupérer les informations de base
        route_info = {
            "path": target_route.path,
            "name": target_route.name,
            "methods": list(target_route.methods) if hasattr(target_route, "methods") else [],
            "tags": target_route.tags if hasattr(target_route, "tags") else []
        }
        
        # Récupérer la docstring de la fonction
        if hasattr(target_route, "endpoint") and callable(target_route.endpoint):
            route_info["description"] = inspect.getdoc(target_route.endpoint)
        
        # Récupérer les informations sur les paramètres
        parameters = []
        if hasattr(target_route, "endpoint") and hasattr(target_route.endpoint, "__annotations__"):
            for param_name, param_type in target_route.endpoint.__annotations__.items():
                if param_name != "return":
                    # Obtenir les informations de paramètre depuis les dépendances si disponibles
                    param_info = {
                        "name": param_name,
                        "type": str(param_type),
                        "required": True,  # Par défaut
                        "kind": "path" if param_name in target_route.path else "query"
                    }
                    
                    # Vérifier les valeurs par défaut
                    if hasattr(target_route.endpoint, "__defaults__") and target_route.endpoint.__defaults__:
                        num_params = len(inspect.signature(target_route.endpoint).parameters)
                        num_defaults = len(target_route.endpoint.__defaults__)
                        if num_params - num_defaults <= list(inspect.signature(target_route.endpoint).parameters.keys()).index(param_name):
                            idx = list(inspect.signature(target_route.endpoint).parameters.keys()).index(param_name) - (num_params - num_defaults)
                            param_info["default"] = str(target_route.endpoint.__defaults__[idx])
                            param_info["required"] = False
                    
                    parameters.append(param_info)
        
        route_info["parameters"] = parameters
        
        # Récupérer le modèle de réponse si disponible
        if hasattr(target_route, "response_model"):
            route_info["response_model"] = str(target_route.response_model)
            
            # Tenter de récupérer le schéma JSON
            if hasattr(target_route.response_model, "schema"):
                schema = target_route.response_model.schema()
                route_info["response_schema"] = schema
        
        return route_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des détails de la route {path}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/database/structure", response_model=DatabaseStructure)
async def get_database_structure():
    """
    Récupère la structure de la base de données SQLite
    
    Cette fonction permet d'obtenir des informations sur les tables, colonnes, indices, etc.
    Utile pour le débogage et l'exploration de la base de données.
    """
    conn = await get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Récupérer la liste des tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row['name'] for row in cursor.fetchall()]
        
        # Structure à retourner
        db_structure = {}
        
        # Pour chaque table, récupérer ses colonnes et autres métadonnées
        for table_name in tables:
            # Informations sur la table
            table_info = {}
            
            # Récupérer les informations sur les colonnes
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for column in cursor.fetchall():
                columns.append({
                    "name": column['name'],
                    "type": column['type'],
                    "notnull": bool(column['notnull']),
                    "dflt_value": column['dflt_value'],
                    "pk": bool(column['pk'])
                })
            
            table_info["columns"] = columns
            
            # Récupérer les informations sur les indices
            cursor.execute(f"PRAGMA index_list({table_name})")
            indices = []
            for index in cursor.fetchall():
                index_name = index['name']
                cursor.execute(f"PRAGMA index_info({index_name})")
                index_columns = [col['name'] for col in cursor.fetchall()]
                indices.append({
                    "name": index_name,
                    "unique": bool(index['unique']),
                    "columns": index_columns
                })
                
            table_info["indices"] = indices
            
            # Récupérer les informations sur les clés étrangères
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = []
            for fk in cursor.fetchall():
                foreign_keys.append({
                    "id": fk['id'],
                    "seq": fk['seq'],
                    "table": fk['table'],
                    "from": fk['from'],
                    "to": fk['to'],
                    "on_update": fk['on_update'],
                    "on_delete": fk['on_delete'],
                    "match": fk['match']
                })
                
            table_info["foreign_keys"] = foreign_keys
            
            # Compter le nombre de lignes
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                table_info["row_count"] = cursor.fetchone()['count']
            except:
                table_info["row_count"] = "N/A"
            
            # Ajouter les informations de la table à la structure
            db_structure[table_name] = table_info
        
        return db_structure
        
    except sqlite3.Error as e:
        logger.error(f"Erreur SQLite lors de la récupération de la structure de la base de données: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur SQLite: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la structure de la base de données: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.post("/database/query", response_model=DatabaseQueryResponse)
async def execute_sql_query(query_request: DatabaseQueryRequest):
    """
    Exécute une requête SQL en lecture seule pour le débogage
    
    Cette fonction permet d'exécuter des requêtes SQL SELECT pour explorer les données.
    Note: Seules les requêtes en lecture seule sont autorisées pour des raisons de sécurité.
    """
    # Vérifier que la requête est en lecture seule (commence par SELECT ou PRAGMA)
    query = query_request.query.strip()
    if not (query.upper().startswith("SELECT") or query.upper().startswith("PRAGMA")):
        raise HTTPException(status_code=400, detail="Seules les requêtes SELECT et PRAGMA sont autorisées.")
    
    conn = await get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Exécuter la requête
        start_time = datetime.now()
        if query_request.params:
            cursor.execute(query, query_request.params)
        else:
            cursor.execute(query)
        
        # Récupérer les résultats
        rows = [dict(row) for row in cursor.fetchall()]
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() * 1000  # en millisecondes
        
        # Préparer la réponse
        response = {
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": execution_time,
            "query": query
        }
        
        return response
        
    except sqlite3.Error as e:
        logger.error(f"Erreur SQLite lors de l'exécution de la requête: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur SQLite: {str(e)}")
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la requête: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()