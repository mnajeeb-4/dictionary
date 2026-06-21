import streamlit as st
import sqlite3
import pandas as pd
import os
from gtts import gTTS
import io

# Page Configuration
st.set_page_config(page_title="English-Urdu Dictionary", layout="wide", page_icon="📚")

DB_NAME = 'dictionary.db'

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictionary_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english_word TEXT UNIQUE,
            urdu_meaning TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM dictionary_words")
    count = cursor.fetchone()[0]
    conn.close()
    
    if count == 0:
        load_data_from_files()

# ==========================================
# 2. FILE LOADING (Handles Excel & CSV Formats)
# ==========================================
def load_data_from_files():
    # Checking for .xlsx or alternative naming formats
    file_name = 'Words.xlsx'
    if not os.path.exists(file_name) and os.path.exists('word.xlsx'):
        file_name = 'word.xlsx'
    elif not os.path.exists(file_name) and os.path.exists('Words.xlsx - A.csv'):
        file_name = 'Words.xlsx - A.csv'
        
    if os.path.exists(file_name):
        try:
            if file_name.endswith('.csv'):
                df = pd.read_csv(file_name, encoding='utf-8')
            else:
                df = pd.read_excel(file_name)
            
            df.columns = [str(col).strip().upper() for col in df.columns]
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                eng = str(row.get('WORDS', '')).strip()
                urdu = str(row.get('MEANING', '')).strip()
                
                if eng and urdu and eng.lower() != 'nan' and urdu.lower() != 'nan':
                    cursor.execute("""
                        INSERT OR IGNORE INTO dictionary_words (english_word, urdu_meaning) 
                        VALUES (?, ?)
                    """, (eng, urdu))
            
            conn.commit()
            conn.close()
            st.sidebar.success("✅ Data successfully loaded!")
        except Exception as e:
            st.sidebar.error(f"File read error: {e}")
    else:
        st.sidebar.warning(f"⚠️ Dataset file not found! Please check file path placement.")

# Initialize Database
init_database()

# ==========================================
# 3. INTERACTIVE WEB UI (ENGLISH)
# ==========================================
st.title("📚 English ⇄ Urdu Task Dictionary")
st.write("Search for specific words to find meanings and listen to pronunciations instantly.")
st.markdown("---")

# Sidebar Search Controls
with st.sidebar:
    st.header("🔍 Search Filters")
    search_mode = st.radio("Search Direction:", ("English ➜ Urdu", "Urdu ➜ English"))
    search_query = st.text_input("Type here to search (Live Search):", "").strip()
    show_favorites = st.checkbox("⭐ Show Favorites Only")

results = []

# Fetch matching records ONLY if a query is typed or if "Show Favorites Only" is checked
if search_query or show_favorites:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if search_mode == "English ➜ Urdu":
        query = "SELECT id, english_word, urdu_meaning, is_favorite FROM dictionary_words WHERE english_word LIKE ?"
    else:
        query = "SELECT id, english_word, urdu_meaning, is_favorite FROM dictionary_words WHERE urdu_meaning LIKE ?"

    params = [f"%{search_query}%"]

    if show_favorites:
        query += " AND is_favorite = 1"

    query += " ORDER BY english_word ASC LIMIT 50"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

# UI Layout Columns
col1, col2 = st.columns([1, 2])

selected_word_data = None

with col1:
    st.subheader("🗂️ Search Results")
    
    # Logic to only display options when a search is actively requested
    if search_query or show_favorites:
        if results:
            options_dict = {}
            for row in results:
                w_id, eng, urdu, fav = row
                star = "⭐ " if fav == 1 else ""
                display_text = f"{star}{eng} ⇄ {urdu}"
                options_dict[display_text] = row
                
            selected_display = st.selectbox("Select from matching words:", list(options_dict.keys()))
            selected_word_data = options_dict[selected_display]
        else:
            st.info("No matching words found.")
    else:
        st.info("🔍 Please type a word in the sidebar search bar to begin.")

with col2:
    if selected_word_data:
        word_id, eng_word, urdu_mean, is_fav = selected_word_data
        
        # English Word Display
        st.markdown(f"""
        <div
