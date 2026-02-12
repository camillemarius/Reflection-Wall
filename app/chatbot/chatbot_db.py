# chatbot_db.py
import mysql.connector
import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "reflection_ai")

def get_connection():
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def setup_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reflections (
        id INT AUTO_INCREMENT PRIMARY KEY,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def get_previous_answers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("SELECT content FROM reflections ORDER BY created_at ASC")
    previous_answers = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return previous_answers

def save_answer(answer_text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("INSERT INTO reflections (content) VALUES (%s)", (answer_text,))
    conn.commit()
    cursor.close()
    conn.close()

def delete_all_entries(reset_id=True):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute("DELETE FROM reflections")
    if reset_id:
        cursor.execute("ALTER TABLE reflections AUTO_INCREMENT = 1")
    conn.commit()
    cursor.close()
    conn.close()

