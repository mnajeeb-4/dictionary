import streamlit as st
import sqlite3
import pandas as pd
import os
from gtts import gTTS
import io

# Page Config (Design aur Layout)
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
    # Table schema aapke columns ke mutabik
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dictionary_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english_word TEXT UNIQUE,
            urdu_meaning TEXT,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    
    # Check karein agar table khali hai toh data load karein
    cursor.execute("SELECT COUNT(*) FROM dictionary_words")
    if cursor.fetchone()[0] == 0:
        load_data_from_your_file(conn)
        
    conn.close()

# ==========================================
# 2. AAPKI FILE SE DATA EXTRACT KARNA
# ==========================================
def load_data_from_files(conn):
    cursor = conn.cursor()
    
    # Aapki file ka exact naam aur path
    file_name = 'Words.xlsx - A.csv'
    
    if os.path.exists(file_name):
        try:
            # CSV file ko read karna (UTF-8 encoding ke sath taaki Urdu kharab na ho)
            df = pd.read_csv(file_name, encoding='utf-8')
            
            # Aapki file ke exact columns: 'WORDS' aur 'MEANING'
            for _, row in df.iterrows():
                eng = str(row['WORDS']).strip()
                urdu = str(row['MEANING']).strip()
                
                # Khali rows ko skip karne ke liye
                if eng and urdu and eng != 'nan' and urdu != 'nan':
                    cursor.execute("""
                        INSERT OR IGNORE INTO dictionary_words (english_word, urdu_meaning) 
                        VALUES (?, ?)
                    """, (eng, urdu))
            
            conn.commit()
            st.sidebar.success("✅ Aapki file se data kamyabi se load ho gaya hai!")
        except Exception as e:
            st.sidebar.error(f"File padhne mein error aaya: {e}")
    else:
        st.sidebar.warning(f"⚠️ '{file_name}' file nahi mili! Please is naam ki file folder mein rakhein.")

# Database initialize karein
init_database()

# ==========================================
# 3. INTERACTIVE WEB UI
# ==========================================
st.title("📚 English ⇄ Urdu Task Dictionary")
st.write("Aapki file ke data par mabni modern dictionary app.")
st.markdown("---")

# Sidebar Filters
with st.sidebar:
    st.header("🔍 Search Filters")
    
    # Requirement: English to Urdu aur Urdu to English Dono Search
    search_mode = st.radio("Search Mode select karein:", ("English ➜ Urdu", "Urdu ➜ English"))
    
    # Live Search Box
    search_query = st.text_input("Yahan type karein (Type here):", "").strip()
    
    # Favorites Option
    show_favorites = st.checkbox("⭐ Sirf Favorites Dikhayein")

# DB se data filter karke nikalna
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

# UI Layout (Two Columns)
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🗂️ Word List")
    if results:
        # Listbox/Selectbox ke liye dictionary banana
        options_dict = {}
        for row in results:
            w_id, eng, urdu, fav = row
            star = "⭐ " if fav == 1 else ""
            display_text = f"{star}{eng} ⇄ {urdu}"
            options_dict[display_text] = row
            
        selected_display = st.selectbox("Koi bhi lafz select karein:", list(options_dict.keys()))
        selected_word_data = options_dict[selected_display]
    else:
        st.info("Koi lafz (word) nahi mila!")
        selected_word_data = None

with col2:
    if selected_word_data:
        word_id, eng_word, urdu_mean, is_fav = selected_word_data
        
        # English Word Card
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 20px; border-radius: 10px; border-left: 5px solid #2b5797; margin-bottom: 15px;">
            <p style="color: grey; font-size: 14px; margin: 0;">English Word</p>
            <h1 style="margin: 0; color: #2b5797;">{eng_word}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Urdu Meaning Card
        st.markdown(f"""
        <div style="background-color: #f1f9f5; padding: 20px; border-radius: 10px; border-left: 5px solid #27ae60; text-align: right;">
            <p style="color: grey; font-size: 14px; margin: 0; text-align: left;">Urdu Meaning / ترجمہ</p>
            <h1 style="margin: 0; color: #27ae60; font-family: 'Arial';">{urdu_mean}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Audio aur Favorite Buttons
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            st.write("🔊 **Pronunciation (Aawaz):**")
            try:
                tts = gTTS(text=eng_word, lang='en')
                audio_fp = io.BytesIO()
                tts.write_to_fp(audio_fp)
                st.audio(audio_fp, format='audio/mp3')
            except Exception as ex:
                st.error("Audio ke liye internet zaroori hai.")
                
        with btn_col2:
            st.write("⭐ **Favorite Action:**")
            fav_button_text = "❌ Favorite se Hatayein" if is_fav == 1 else "⭐ Favorite Banayein"
            if st.button(fav_button_text, use_container_width=True):
                new_status = 0 if is_fav == 1 else 1
                cursor.execute("UPDATE dictionary_words SET is_favorite = ? WHERE id = ?", (new_status, word_id))
                conn.commit()
                st.rerun()

conn.close()
