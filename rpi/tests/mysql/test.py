# mysql_example.py
import mysql.connector
import os
from dotenv import load_dotenv

# 🔹 Lade Umgebungsvariablen aus .env
load_dotenv()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "test_db")

# 🔹 Verbindung zur MySQL-Datenbank herstellen
def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )

# 🔹 Datenbank und Tabelle erstellen
def setup_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            text_content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("Datenbank und Tabelle bereit.")

# 🔹 Eintrag speichern
def save_note(text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("INSERT INTO notes (text_content) VALUES (%s)", (text,))
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Eintrag gespeichert: {text}")

# 🔹 Alle Einträge abrufen
def get_notes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("SELECT id, text_content, created_at FROM notes ORDER BY created_at ASC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

# 🔹 Testlauf
if __name__ == "__main__":
    setup_database()
    
    # Beispiel: neuen Eintrag speichern
    save_note("Hallo Welt! Das ist ein Testeintrag.")
    
    # Alle Einträge ausgeben
    print("\nAlle gespeicherten Einträge:")
    for id_, text, ts in get_notes():
        print(f"{id_} | {ts} | {text}")