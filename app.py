import streamlit as st
import sqlite3
import pandas as pd
import os
from gtts import gTTS
import io

# Page Configuration
st.set_page_config(page_title="English-Urdu Dictionary", layout="wide", page_icon="📚")

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def get_db_connection():
    conn = sqlite3.connect('dictionary.db')
    return conn

def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Table structure aapke data ke mutabik
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictionary_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english_word TEXT UNIQUE,
            urdu_meaning TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    
    # Check karein agar data pehle se maujood nahi hai toh load karein
    cursor.execute("SELECT COUNT(*) FROM dictionary_words")
    if cursor.fetchone()[0] == 0:
        load_data_from_files(conn)  # <-- Yeh naam ab bilkul sahi hai!
        
    conn.close()

# ==========================================
# 2. AAPKI FILE SE DATA LOAD KARNA
# ==========================================
def load_data_from_files(conn):
    cursor = conn.cursor()
    
    # Aapki file ka sahi naam
    file_name = 'Words.xlsx - A.csv'
    
    if os.path.exists(file_name):
        try:
            # CSV file ko read karna (Urdu fonts ke liye utf-8 zaroori hai)
            df = pd.read_csv(file_name, encoding='utf-8')
            
            # Aapki file ke columns: 'WORDS' aur 'MEANING'
            for _, row in df.iterrows():
                eng = str(row['WORDS']).strip()
                urdu = str(row['MEANING']).strip()
                
                # Khali entries ko filter karna
                if eng and urdu and eng != 'nan' and urdu != 'nan':
                    cursor.execute("""
                        INSERT OR IGNORE INTO dictionary_words (english_word, urdu_meaning) 
                        VALUES (?, ?)
                    """, (eng, urdu))
            
            conn.commit()
            st.sidebar.success("✅ Data file se kamyabi se load ho gaya hai!")
        except Exception as e:
            st.sidebar.error(f"File read karne mein error: {e}")
    else:
        st.sidebar.warning(f"⚠️ '{file_name}' nahi mili! Please is file ko app.py ke sath rakhein.")

# Database initialize karein
init_database()

# ==========================================
# 3. INTERACTIVE WEB UI
# ==========================================
st.title("📚 English ⇄ Urdu Task Dictionary")
st.write("Aapki csv file ke data par mabni advanced dictionary.")
st.markdown("---")

# Sidebar Search Controls
with st.sidebar:
    st.header("🔍 Search Filters")
    search_mode = st.radio("Search Direction:", ("English ➜ Urdu", "Urdu ➜ English"))
    search_query = st.text_input("Yahan type karein (Live Search):", "").strip()
    show_favorites = st.checkbox("⭐ Sirf Favorites Dikhayein")

# DB se filtered content nikalna
conn = get_db_connection()
cursor = conn.cursor()

if search_mode == "English ➜ Urdu":
    query = "SELECT id, english_word, urdu_meaning, is_favorite FROM dictionary_words WHERE english_word LIKE ?"
    params = [f"%{search_query}%"]
else:
    query = "SELECT id, english_word, urdu_meaning, is_favorite FROM dictionary_words WHERE urdu_meaning LIKE ?"
    params = [f"%{search_query}%"]

if show_favorites:
    query += " AND is_favorite = 1"

query += " ORDER BY english_word ASC LIMIT 100"

cursor.execute(query, params)
results = cursor.fetchall()

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
            
        selected_display = st.selectbox("Lafz select karein:", list(options_dict.keys()))
        selected_word_data = options_dict[selected_display]
    else:
        st.info("Koi word nahi mila!")
        selected_word_data = None

with col2:
    if selected_word_data:
        word_id, eng_word, urdu_mean, is_fav = selected_word_data
        
        # English Card
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border-left: 5px solid #2b5797; margin-bottom: 15px;">
            <p style="color: grey; font-size: 14px; margin: 0;">English Word</p>
            <h1 style="margin: 0; color: #2b5797;">{eng_word}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Urdu Card
        st.markdown(f"""
        <div style="background-color: #f1f9f5; padding: 20px; border-radius: 10px; border-left: 5px solid #27ae60; text-align: right;">
            <p style="color: grey; font-size: 14px; margin: 0; text-align: left;">Urdu Meaning / ترجمہ</p>
            <h1 style="margin: 0; color: #27ae60; font-family: 'Arial';">{urdu_mean}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Interactive Feature Row
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            st.write("🔊 **Pronunciation (Aawaz):**")
            try:
                tts = gTTS(text=eng_word, lang='en')
                audio_fp = io.BytesIO()
                tts.write_to_fp(audio_fp)
                st.audio(audio_fp, format='audio/mp3')
            except Exception as ex:
                st.error("Audio ke liye internet connection zaroori hai.")
                
        with btn_col2:
            st.write("⭐ **Favorite Action:**")
            fav_button_text = "❌ Favorite se Hatayein" if is_fav == 1 else "⭐ Favorite Banayein"
            if st.button(fav_button_text, use_container_width=True):
                new_status = 0 if is_fav == 1 else 1
                cursor.execute("UPDATE dictionary_words SET is_favorite = ? WHERE id = ?", (new_status, word_id))
                conn.commit()
                st.rerun()

conn.close()
