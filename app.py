import streamlit as st
import sqlite3
import pandas as pd
import os
from gtts import gTTS
import io

# Page Configuration (Attractive Web UI Layout)
st.set_page_config(page_title="English-Urdu Dictionary", layout="wide", page_icon="📚")

# ==========================================
# 1. DATABASE SETUP (SQLite3)
# ==========================================
def get_db_connection():
    conn = sqlite3.connect('dictionary.db')
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Table schema according to requirements
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english_word TEXT UNIQUE,
            urdu_meaning TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    
    # Check karein agar table khali hai toh data load karein
    cursor.execute("SELECT COUNT(*) FROM words")
    if cursor.fetchone()[0] == 0:
        load_data_from_files(conn)
        
    conn.close()

# ==========================================
# 2. DATA EXTRACTION LOGIC (CSV/Excel Se)
# ==========================================
def load_data_from_files(conn):
    cursor = conn.cursor()
    data_loaded = False
    
    # Aapki zip file ke mutabik checks
    possible_files = ['Words.xlsx - A.csv', 'Words.xlsx', 'data.xlsx']
    
    for file_name in possible_files:
        if os.path.exists(file_name):
            try:
                if file_name.endswith('.csv'):
                    df = pd.read_csv(file_name)
                else:
                    df = pd.read_excel(file_name)
                
                # Column names ko normalize karna (WORDS aur MEANING aapke file mein hain)
                df.columns = [str(c).strip().upper() for c in df.columns]
                
                eng_col = 'WORDS' if 'WORDS' in df.columns else df.columns[1]
                urdu_col = 'MEANING' if 'MEANING' in df.columns else df.columns[2]
                
                for _, row in df.iterrows():
                    eng = str(row[eng_col]).strip()
                    urdu = str(row[urdu_col]).strip()
                    if eng and urdu and eng != 'nan' and urdu != 'nan':
                        cursor.execute("INSERT OR IGNORE INTO words (english_word, urdu_meaning) VALUES (?, ?)", (eng, urdu))
                
                conn.commit()
                data_loaded = True
                break
            except Exception as e:
                st.sidebar.error(f"File load karne mein error: {e}")
                
    # Fallback Data agar koi file na mile
    if not data_loaded:
        fallback = [("apple", "سیب"), ("book", "کتاب"), ("computer", "کمپیوٹر"), ("water", "پانی")]
        for eng, urdu in fallback:
            cursor.execute("INSERT OR IGNORE INTO words (english_word, urdu_meaning) VALUES (?, ?)", (eng, urdu))
        conn.commit()

# DB Table Initialization
init_database()

# ==========================================
# 3. STREAMLIT INTERACTIVE UI
# ==========================================
st.title("📚 Interactive English ⇄ Urdu Dictionary")
st.write("Welcome to your modern vocabulary learning app.")
st.markdown("---")

# Layout divided into Sidebar (Filters) and Main Area (Results)
with st.sidebar:
    st.header("⚙️ Search Controls")
    
    # Requirement: Live Search & Filtering Direction
    search_mode = st.radio("Search Direction / سمت:", ("English ➜ Urdu", "Urdu ➜ English"))
    
    # Live Input Box
    search_query = st.text_input("Type to search / لفظ لکھیں:", "").strip()
    
    # Requirement: Favorites Filter Toggle
    show_favorites = st.checkbox("⭐ Show Favorites Only")

# Fetching Data from Database based on user interaction
conn = get_db_connection()
cursor = conn.cursor()

if search_mode == "English ➜ Urdu":
    query = "SELECT id, english_word, urdu_meaning, is_favorite FROM words WHERE english_word LIKE ?"
    params = [f"%{search_query}%"]
else:
    query = "SELECT id, english_word, urdu_meaning, is_favorite FROM words WHERE urdu_meaning LIKE ?"
    params = [f"%{search_query}%"]

if show_favorites:
    query += " AND is_favorite = 1"

query += " ORDER BY english_word ASC LIMIT 100" # Performance optimized

cursor.execute(query, params)
results = cursor.fetchall()

# Display List and Meanings
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🗂️ Word List")
    if results:
        # Create formatting display text for list options
        options_dict = {}
        for row in results:
            w_id, eng, urdu, fav = row
            star = "⭐ " if fav == 1 else ""
            display_text = f"{star}{eng} ⇄ {urdu}"
            options_dict[display_text] = row
            
        selected_display = st.selectbox("Select a word:", list(options_dict.keys()), label_visibility="collapsed")
        selected_word_data = options_dict[selected_display]
    else:
        st.info("Koi word nahi mila!")
        selected_word_data = None

with col2:
    if selected_word_data:
        word_id, eng_word, urdu_mean, is_fav = selected_word_data
        
        # Word Card Layout
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border-left: 5px solid #2b5797;">
            <p style="color: grey; font-size: 14px; margin: 0;">English Word</p>
            <h1 style="margin: 0; color: #2b5797;">{eng_word}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        st.markdown(f"""
        <div style="background-color: #f1f9f5; padding: 20px; border-radius: 10px; border-left: 5px solid #27ae60; text-align: right;">
            <p style="color: grey; font-size: 14px; margin: 0; text-align: left;">Urdu Meaning / ترجمہ</p>
            <h1 style="margin: 0; color: #27ae60; font-family: 'Jameel Noori Nastaleeq', 'Arial';">{urdu_mean}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Action Row (Voice Pronunciation & Favorites toggle)
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            st.write("🔊 **Pronunciation (Audio):**")
            try:
                # Online secure voice conversion via Google TTS for Web browser
                tts = gTTS(text=eng_word, lang='en', slow=False)
                audio_fp = io.BytesIO()
                tts.write_to_fp(audio_fp)
                st.audio(audio_fp, format='audio/mp3')
            except Exception as ex:
                st.error("Audio feature ke liye Internet connection lazmi hai.")
                
        with btn_col2:
            st.write("⭐ **Favorite Action:**")
            fav_button_text = "❌ Remove from Favorites" if is_fav == 1 else "⭐ Add to Favorites"
            if st.button(fav_button_text, use_container_width=True):
                new_status = 0 if is_fav == 1 else 1
                cursor.execute("UPDATE words SET is_favorite = ? WHERE id = ?", (new_status, word_id))
                conn.commit()
                st.rerun() # UI refresh to display changes immediately

conn.close()
