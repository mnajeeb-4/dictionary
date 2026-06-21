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
# 2. FIXED FILE LOADING (Handles Real Excel)
# ==========================================
def load_data_from_files():
    file_name = 'Words.xlsx'
    if not os.path.exists(file_name) and os.path.exists('word.xlsx'):
        file_name = 'word.xlsx'
        
    if os.path.exists(file_name):
        try:
            # FIX: Using pd.read_excel because your file is a real Excel spreadsheet (.xlsx)
            df = pd.read_excel(file_name)
            
            # Standardize column names to uppercase to match 'WORDS' and 'MEANING'
            df.columns = [str(col).strip().upper() for col in df.columns]
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                # Read using the exact column keys from your file
                eng = str(row.get('WORDS', '')).strip()
                urdu = str(row.get('MEANING', '')).strip()
                
                if eng and urdu and eng.lower() != 'nan' and urdu.lower() != 'nan':
                    cursor.execute("""
                        INSERT OR IGNORE INTO dictionary_words (english_word, urdu_meaning) 
                        VALUES (?, ?)
                    """, (eng, urdu))
            
            conn.commit()
            conn.close()
            st.sidebar.success("✅ Data successfully loaded from Excel file!")
        except Exception as e:
            st.sidebar.error(f"File read error: {e}")
    else:
        st.sidebar.warning(f"⚠️ '{file_name}' not found! Place it in the same directory as app.py.")

# Initialize Database
init_database()

# ==========================================
# 3. INTERACTIVE WEB UI (ENGLISH)
# ==========================================
st.title("📚 English ⇄ Urdu Task Dictionary")
st.write("Advanced interactive dictionary powered by your Words dataset.")
st.markdown("---")

# Sidebar Search Controls
with st.sidebar:
    st.header("🔍 Search Filters")
    search_mode = st.radio("Search Direction:", ("English ➜ Urdu", "Urdu ➜ English"))
    search_query = st.text_input("Type here to search (Live Search):", "").strip()
    show_favorites = st.checkbox("⭐ Show Favorites Only")

# Fetch filtered content from DB
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

if search_mode == "English ➜ Urdu":
    query = "SELECT id, english_word, urdu_meaning, is_favorite FROM dictionary_words WHERE english_word LIKE ?"
else:
    query = "SELECT id, english_word, urdu_meaning, is_favorite FROM dictionary_words WHERE urdu_meaning LIKE ?"

params = [f"%{search_query}%"]

if show_favorites:
    query += " AND is_favorite = 1"

query += " ORDER BY english_word ASC LIMIT 100"

cursor.execute(query, params)
results = cursor.fetchall()
conn.close()

# UI Layout Columns
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🗂️ Word List")
    if results:
        options_dict = {}
        for row in results:
            w_id, eng, urdu, fav = row
            star = "⭐ " if fav == 1 else ""
            display_text = f"{star}{eng} ⇄ {urdu}"
            options_dict[display_text] = row
            
        selected_display = st.selectbox("Select a word:", list(options_dict.keys()))
        selected_word_data = options_dict[selected_display]
    else:
        st.info("No words found matching your search.")
        selected_word_data = None

with col2:
    if selected_word_data:
        word_id, eng_word, urdu_mean, is_fav = selected_word_data
        
        # English Card View
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border-left: 5px solid #2b5797; margin-bottom: 15px;">
            <p style="color: grey; font-size: 14px; margin: 0;">English Word</p>
            <h1 style="margin: 0; color: #2b5797;">{eng_word}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Urdu Card View
        st.markdown(f"""
        <div style="background-color: #f1f9f5; padding: 20px; border-radius: 10px; border-left: 5px solid #27ae60; text-align: right;">
            <p style="color: grey; font-size: 14px; margin: 0; text-align: left;">Urdu Meaning / ترجمہ</p>
            <h1 style="margin: 0; color: #27ae60; font-family: 'Arial';">{urdu_mean}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Features Action Row
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            st.write("🔊 **Pronunciation:**")
            try:
                tts = gTTS(text=eng_word, lang='en')
                audio_fp = io.BytesIO()
                tts.write_to_fp(audio_fp)
                audio_fp.seek(0)
                st.audio(audio_fp.read(), format='audio/mp3')
            except Exception as ex:
                st.error("Internet connection required for audio pronunciation.")
                
        with btn_col2:
            st.write("⭐ **Favorite Action:**")
            fav_button_text = "❌ Remove from Favorites" if is_fav == 1 else "⭐ Add to Favorites"
            if st.button(fav_button_text, use_container_width=True):
                new_status = 0 if is_fav == 1 else 1
                
                conn_write = sqlite3.connect(DB_NAME)
                cursor_write = conn_write.cursor()
                cursor_write.execute("UPDATE dictionary_words SET is_favorite = ? WHERE id = ?", (new_status, word_id))
                conn_write.commit()
                conn_write.close()
                
                st.rerun()
