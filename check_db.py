#!/usr/bin/env python
"""
Script de diagnostic pour vérifier l'état de la base de données
"""
import os
import sqlite3

def get_db_connection(db_path):
    """Établit et retourne une connexion à la base de données SQLite"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def check_database(db_path):
    """Vérifie l'état de la base de données et affiche un rapport"""
    print(f"Vérification de la base de données: {db_path}")
    
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        # 1. Vérifier les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nTables trouvées: {', '.join(tables)}")
        
        # 2. Compter les entrées dans les tables principales
        counts = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                counts[table] = count
            except Exception as e:
                counts[table] = f"Erreur: {str(e)}"
        
        print("\nNombre d'enregistrements par table:")
        for table, count in counts.items():
            print(f"- {table}: {count}")
        
        # 3. Vérifier spécifiquement les tags
        if "tags" in tables:
            cursor.execute("SELECT id, nom FROM tags")
            tags = [dict(row) for row in cursor.fetchall()]
            print(f"\nTags présents ({len(tags)}):")
            for tag in tags:
                cursor.execute("SELECT COUNT(*) FROM entry_tags WHERE tag_id = ?", (tag["id"],))
                usage_count = cursor.fetchone()[0]
                print(f"- ID: {tag['id']}, Nom: {tag['nom']}, Utilisations: {usage_count}")
        
        # 4. Vérifier les entrées importées
        cursor.execute("SELECT COUNT(*) FROM journal_entries WHERE source_document IS NOT NULL AND source_document != ''")
        import_count = cursor.fetchone()[0]
        print(f"\nEntrées importées: {import_count}")
        
        if import_count > 0:
            cursor.execute("SELECT DISTINCT source_document FROM journal_entries WHERE source_document IS NOT NULL AND source_document != ''")
            sources = [row[0] for row in cursor.fetchall()]
            print(f"Sources d'import: {', '.join(sources)}")
            
            # Vérifier les tags liés aux imports
            cursor.execute("""
            SELECT DISTINCT t.id, t.nom
            FROM tags t
            JOIN entry_tags et ON t.id = et.tag_id
            JOIN journal_entries j ON et.entry_id = j.id
            WHERE j.source_document IS NOT NULL AND j.source_document != ''
            """)
            import_tags = [dict(row) for row in cursor.fetchall()]
            
            print(f"\nTags liés aux imports ({len(import_tags)}):")
            for tag in import_tags:
                print(f"- {tag['nom']} (ID: {tag['id']})")
        
        conn.close()
        print("\nVérification terminée.")
        
    except Exception as e:
        print(f"Erreur lors de la vérification de la base de données: {str(e)}")

if __name__ == "__main__":
    # Identifier la base de données
    db_path = None
    if os.path.exists("backend/data/memoire.db"):
        db_path = "backend/data/memoire.db"
    elif os.path.exists("data/memoire.db"):
        db_path = "data/memoire.db"
    
    if not db_path:
        print("Erreur: Base de données non trouvée!")
        exit(1)
    
    check_database(db_path)