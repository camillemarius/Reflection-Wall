# chatbot_db.py
import mysql.connector
import os
from dotenv import load_dotenv

# 🔹 Verfügbare Datenbanken und Tabellen
AVAILABLE_DATABASES = {
    "quiz": "quiz_db",
    "reflection": "reflection_db"
}
TABLES = {
    "quiz": "questions",
    "reflection": "reflections"
}

# 🔹 Umgebungsvariablen laden
load_dotenv()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


# 🔹 Helfer: DB-Name holen
def get_db_name(db_key):
    db_name = AVAILABLE_DATABASES.get(db_key)
    if not db_name:
        raise ValueError(f"Unbekannte Datenbank: {db_key}")
    return db_name

# 🔹 Helfer: Tabellennamen holen
def get_table_name(db_key):
    table_name = TABLES.get(db_key)
    if not table_name:
        raise ValueError(f"Unbekannte Tabelle für DB-Key: {db_key}")
    return table_name


# 🔹 Verbindung herstellen
def get_connection(db_name=None):
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=db_name
    )
    return conn


def setup_db(db_key):
    db_name = get_db_name(db_key)
    table_name = get_table_name(db_key)  # 👈 hier das neue Mapping nutzen

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    cursor.execute(f"USE {db_name}")

    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()


# 🔹 Alle bisherigen Einträge holen
def get_previous_answers(db_key):
    db_name = get_db_name(db_key)
    table_name = get_table_name(db_key)

    conn = get_connection(db_name)
    cursor = conn.cursor()

    cursor.execute(f"SELECT content FROM {table_name} ORDER BY created_at ASC")
    previous_answers = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return previous_answers


# 🔹 Antwort speichern
def save_answer(answer_text, db_key):
    db_name = get_db_name(db_key)
    table_name = get_table_name(db_key)

    conn = get_connection(db_name)
    cursor = conn.cursor()

    cursor.execute(
        f"INSERT INTO {table_name} (content) VALUES (%s)",
        (answer_text,)
    )

    conn.commit()
    cursor.close()
    conn.close()


# 🔹 Alle Einträge löschen
def delete_all_entries(db_key, reset_id=True):
    db_name = get_db_name(db_key)
    table_name = get_table_name(db_key)

    conn = get_connection(db_name)
    cursor = conn.cursor()

    cursor.execute(f"DELETE FROM {table_name}")

    if reset_id:
        cursor.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = 1")

    conn.commit()
    cursor.close()
    conn.close()


# 🔹 Alle Datenbanken auflisten
def list_databases():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SHOW DATABASES")
    dbs = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return dbs


# 🔹 Nur die verfügbaren App-DBs
def list_available_databases():
    return AVAILABLE_DATABASES