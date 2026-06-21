import io                   # audio bytes ko file ki tarah padhne ke liye
import os                   # file exist check ke liye
from pathlib import Path    # file paths ke liye

import streamlit as st      # web interface banana ke liye

# SQLAlchemy -- database ke saath kaam karne ke liye (ORM)
from sqlalchemy import create_engine, Column, Integer, String, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql.expression import func  # random word ke liye

# SpeechRecognition -- microphone ki awaaz ko text mein badalne ke liye
import speech_recognition as sr

# Pandas aur PyPDF2 -- optional hain, Excel/PDF se data import ke liye
try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

try:
    import PyPDF2
    PYPDF2_OK = True
except ImportError:
    PYPDF2_OK = False


# ==============================================================
# SECTION 2 -- DATABASE MODEL (ORM)
# Words table ka Python blueprint
# ==============================================================

# Yeh base class hai jisse Word class inherit karti hai
Base = declarative_base()

# Database file ka path -- app.py ke saath "data" folder mein
DB_FILE = Path(__file__).parent / "data" / "words.db"


class Word(Base):
    """
    Database ki 'Words' table ka ORM model.

    Ek Word object = table ki ek row.

    Columns:
        Sr           -- auto-increment serial number (primary key)
        english_word -- English word  (e.g., 'abandon')
        urdu_meaning -- Urdu meaning  (e.g., 'چھوڑنا')
        is_favorite  -- bookmark flag  (True = favorite hai, False = nahi)
    """
    __tablename__ = "Words"

    Sr           = Column("Sr",          Integer, primary_key=True, autoincrement=True)
    english_word = Column("WORDS",       String,  nullable=False)
    urdu_meaning = Column("MEANING",     String,  nullable=False)
    is_favorite  = Column("is_favorite", Boolean, default=False)


# ==============================================================
# SECTION 3 -- DATABASE SETUP
# Connection banana, schema migrate karna, session return karna
# ==============================================================

@st.cache_resource
def db_connect():
    """
    Database se ek baar connect karta hai aur session return karta hai.

    @st.cache_resource: yeh function sirf pehli baar chalta hai.
    Dobara page load hone par cached session return ho jaata hai.
    """
    # Step 1 -- Engine banao
    engine = create_engine(f"sqlite:///{DB_FILE}", echo=False)

    # Step 2 -- is_favorite column add karo (safe migration)
    # Agar column pehle se hai to exception aayega -- ignore karo
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE Words ADD COLUMN is_favorite BOOLEAN DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            pass  # column pehle se exist karta hai -- theek hai

    # Step 3 -- Session banao
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    # Step 4 -- Khaali DB mein data bharo
    if session.query(Word).count() == 0:
        db_populate(session)

    return session


# ==============================================================
# SECTION 4 -- DATA IMPORT
# Excel / PDF / built-in sample se words bharna
# ==============================================================

def db_populate(session):
    """
    Database mein words bharne ke 3 tarike:

    Tarika A -- data.xlsx  (agar file hai aur pandas installed hai)
    Tarika B -- data.pdf   (agar file hai aur PyPDF2 installed hai)
    Tarika C -- built-in sample words (hamesha kaam karta hai)

    data.xlsx ya data.pdf ko app.py ke saath rakhein.
    """
    imported = False

    #    Tarika A: Excel file                                  
    if os.path.exists("data.xlsx") and PANDAS_OK:
        try:
            df = pd.read_excel("data.xlsx")
            eng_col = urdu_col = None

            # Column naam flexible dhundho
            for col in df.columns:
                name = str(col).lower()
                if name in ["words", "word", "english", "english_word"]:
                    eng_col = col
                if name in ["meaning", "meanings", "urdu", "urdu_meaning"]:
                    urdu_col = col

            if eng_col and urdu_col:
                for _, row in df.iterrows():
                    eng  = str(row[eng_col]).strip()
                    urdu = str(row[urdu_col]).strip()
                    if eng and urdu and eng != "nan" and urdu != "nan":
                        if not session.query(Word).filter_by(english_word=eng).first():
                            session.add(Word(english_word=eng, urdu_meaning=urdu))
                session.commit()
                imported = True
        except Exception as e:
            st.warning(f"data.xlsx nahi padh saka: {e}")

    #    Tarika B: PDF file                                    
    if not imported and os.path.exists("data.pdf") and PYPDF2_OK:
        try:
            with open("data.pdf", "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    for line in page_text.split("\n"):
                        sep = ":" if ":" in line else ("-" if "-" in line else None)
                        if sep:
                            parts = line.split(sep, 1)
                            eng, urdu = parts[0].strip(), parts[1].strip()
                            if eng and urdu:
                                if not session.query(Word).filter_by(english_word=eng).first():
                                    session.add(Word(english_word=eng, urdu_meaning=urdu))
            session.commit()
            imported = True
        except Exception as e:
            st.warning(f"data.pdf nahi padh saka: {e}")

    #    Tarika C: Built-in sample (fallback)                  
    if session.query(Word).count() == 0:
        samples = [
            ("apple",     "سیب"),
            ("book",      "کتاب"),
            ("knowledge", "علم"),
            ("water",     "پانی"),
            ("beautiful", "خوبصورت"),
            ("cat",       "بلی"),
            ("computer",  "کمپیوٹر"),
            ("software",  "سافٹ ویئر"),
        ]
        for eng, urdu in samples:
            session.add(Word(english_word=eng, urdu_meaning=urdu))
        session.commit()


# ==============================================================
# SECTION 5 -- DATABASE QUERIES
# Search, favorites, browse ke liye helper functions
# ==============================================================

@st.cache_data(show_spinner=False)
def db_search(query: str, direction: str):
    """
    Words dhundne ka function.

    query     -- jo user ne likha ya bola (jaise 'apple' ya 'سیب')
    direction -- "eng" ya "urdu"
              "eng"  = English column mein dhundho
              "urdu" = Urdu column mein dhundho

    Returns -- Word objects ki list (max 200 results)
    """
    db  = st.session_state.db
    q   = query.strip()

    if direction == "eng":
        # English word mein dhundho -- case insensitive, partial match
        return (
            db.query(Word)
            .filter(Word.english_word.ilike(f"%{q}%"))
            .order_by(Word.english_word)
            .limit(200)
            .all()
        )
    else:
        # Urdu meaning mein dhundho
        return (
            db.query(Word)
            .filter(Word.urdu_meaning.contains(q))
            .order_by(Word.Sr)
            .limit(200)
            .all()
        )


@st.cache_data(show_spinner=False)
def db_get_one(english: str):
    """
    Exact English word se ek Word object laata hai.
    Agar nahi mila to None return karta hai.
    """
    return (
        st.session_state.db
        .query(Word)
        .filter(Word.english_word.ilike(english.strip()))
        .first()
    )


@st.cache_data(show_spinner=False)
def db_favorites():
    """Saare favorite words ki list return karta hai."""
    return st.session_state.db.query(Word).filter_by(is_favorite=True).all()


@st.cache_data(show_spinner=False)
def db_by_prefix(prefix: str):
    """
    Diye gaye prefix se shuru hone wale saare words return karta hai.
    Jaise: prefix='ab' -> [ab, abacus, abandon, abbreviate, ...]
    """
    return (
        st.session_state.db
        .query(Word)
        .filter(Word.english_word.ilike(f"{prefix}%"))
        .order_by(Word.english_word)
        .all()
    )


@st.cache_data(show_spinner=False)
def db_prefix_counts():
    """
    Har 2-letter prefix ke liye word count return karta hai.
    Browse page ke dropdown ke liye use hota hai.
    Jaise: {'ab': 399, 'ac': 472, 'ad': 331, ...}
    """
    from collections import Counter
    rows   = st.session_state.db.query(Word.english_word).all()
    counts = Counter(w[0][:2].lower() for w in rows if len(w[0]) >= 2)
    return dict(sorted(counts.items()))


@st.cache_data(show_spinner=False)
def db_random():
    """Database se ek random word nikalata hai -- Word of the Day ke liye."""
    return st.session_state.db.query(Word).order_by(func.random()).first()


def db_toggle_favorite(word: Word):
    """
    Word ko favorite banata hai ya un-favorite karta hai.

    is_favorite = False  ->  True  (Add to Favorites)
    is_favorite = True   ->  False (Remove from Favorites)

    Changes database mein save ho jaate hain.
    Cache clear karna zaruri hai warna purana data dikhega.
    """
    db           = st.session_state.db
    word.is_favorite = not word.is_favorite
    db.commit()

    # Caches clear karo -- naye data ke saath page dobara render ho
    db_search.clear()
    db_get_one.clear()
    db_favorites.clear()

    st.rerun()


# ==============================================================
# SECTION 6 -- HISTORY
# Is session mein recently dekhe words track karna
# ==============================================================

def history_add(english_word: str):
    """
    Ek word ko session ki history mein add karta hai.
    History browser band hone par khud clear ho jaati hai.
    Maximum 50 words store hote hain.
    """
    history = st.session_state.setdefault("history", [])
    if english_word not in history:
        history.append(english_word)
    if len(history) > 50:
        history.pop(0)  # sabse pehla hata do jab 50 se zyada ho


# ==============================================================
# SECTION 7 -- DISPLAY BLOCKS
# Screen par word dikhane ke liye reusable functions
# ==============================================================

def show_word_full(word: Word):
    """
    Ek word ki poori detail dikhata hai.

    Dikhata hai:
    - English word (bada, header mein)
    - Serial number
    - Urdu meaning (info box mein)
    - Favorite add/remove button
    """
    icon = "⭐ " if word.is_favorite else ""

    st.subheader(f"{icon}{word.english_word}")
    st.caption(f"Word No. {word.Sr}")
    st.divider()

    st.write("**Urdu Meaning — اردو معنی**")
    st.info(word.urdu_meaning)

    # Favorite button -- click karne par toggle hota hai
    if word.is_favorite:
        if st.button("⭐ Remove from Favorites", key=f"fav_{word.Sr}"):
            db_toggle_favorite(word)
    else:
        if st.button("☆ Add to Favorites", key=f"fav_{word.Sr}"):
            db_toggle_favorite(word)

    # History mein add karo
    history_add(word.english_word)


def show_word_card(word: Word):
    """
    Ek word ka chhota preview card dikhata hai (expandable).
    Search results aur Browse mein use hota hai.
    Click karke expand karo to meaning aur button dikh jata hai.
    """
    icon  = "⭐ " if word.is_favorite else "📝 "
    label = f"{icon}{word.english_word}"

    with st.expander(label):
        st.write(word.urdu_meaning)

        btn_label = "⭐ Remove" if word.is_favorite else "☆ Favorite"
        if st.button(btn_label, key=f"card_{word.Sr}"):
            db_toggle_favorite(word)


def show_results(query: str, results: list):
    """
    Search results screen par dikhata hai.

    Agar exact match mili -> us word ki poori detail pehle dikhao,
    baaki milte-julte words neeche cards mein.

    Agar sirf partial match mili -> saari results cards mein.
    """
    if not results:
        st.warning(f'**"{query}"** ke liye koi result nahi mila.')
        return

    # Exact match dhundho
    exact = None
    for r in results:
        if r.english_word.lower() == query.strip().lower():
            exact = r
            break

    if exact:
        # Poori detail dikhao
        show_word_full(exact)

        # Milte-julte words bhi neeche dikhao
        others = [r for r in results if r.Sr != exact.Sr]
        if others:
            st.write(f"**Milte-julte {len(others)} words:**")
            for w in others[:25]:
                show_word_card(w)
    else:
        # Sirf partial results -- cards mein
        st.write(f"**{len(results)} results mile:**")
        for w in results[:30]:
            show_word_card(w)
        if len(results) > 30:
            st.info("30 results dikh rahe hain. Zyada exact likhkar narrow karein.")


# ==============================================================
# SECTION 8 -- VOICE HELPER
# Microphone ki audio ko text mein badalna
# ==============================================================

def voice_to_text(audio_bytes: bytes, language: str) -> str:
    """
    Microphone se recorded audio ko text mein convert karta hai.

    audio_bytes -- st.audio_input() se mila WAV audio data (bytes)
    language    -- "en-US" ya "ur-PK" (konsi zubaan mein bol rahe hain)

    Returns -- text string
    Raises  -- sr.UnknownValueError agar awaaz samajh na aayi
              sr.RequestError agar internet nahi hai
    """
    recognizer = sr.Recognizer()

    # Bytes ko AudioFile object mein convert karo
    audio_file = sr.AudioFile(io.BytesIO(audio_bytes))

    with audio_file as source:
        # Background noise ke liye adjust karo
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        audio_data = recognizer.record(source)

    # Google ka free speech recognition use karo -- koi API key nahi chahiye
    return recognizer.recognize_google(audio_data, language=language).strip()


# ==============================================================
# SECTION 9 -- PAGE: TEXT SEARCH
# ==============================================================

def page_text_search():
    """
    Text Search Page.

    User kuch type karta hai -> database mein dhundhte hain ->
    screen par results dikhate hain.

    Supports:
    - English -> Urdu  (English likhkar Urdu pao)
    - Urdu -> English  (Urdu likhkar English word pao)
    """
    st.subheader("🔍 Text Search — الفاظ تلاش کریں")

    # Search direction choose karo
    direction_label = st.radio(
        "Kis direction mein search karein",
        ["English → Urdu", "Urdu → English"],
        horizontal=True
    )

    # "English -> Urdu" -> eng, "Urdu -> English" -> urdu
    direction = "eng" if "English → Urdu" in direction_label else "urdu"

    # Search box
    placeholder = "English word likhein…" if direction == "eng" else "اردو میں لکھیں…"
    query = st.text_input(
        "Search karo",
        placeholder=placeholder,
        label_visibility="collapsed"
    )

    st.divider()

    # Kuch nahi likha -> Word of the Day dikhao
    if not query or not query.strip():
        wotd = db_random()
        if wotd:
            st.write("### 📖 Word of the Day — آج کا لفظ")
            show_word_full(wotd)
        return

    # Search karo aur results dikhao
    results = db_search(query.strip(), direction)
    show_results(query.strip(), results)


# ==============================================================
# SECTION 10 -- PAGE: VOICE SEARCH
# ==============================================================

def page_voice_search():
    """
    Voice Search Page -- awaaz se search.

    Kaise kaam karta hai (pure Python):
    1. st.audio_input()     -> browser microphone se record karo
    2. voice_to_text()      -> SpeechRecognition se text mein badlo
    3. db_search() ya       -> database mein dhundho
       db_get_one()
    4. show_results()       -> screen par dikhao

    Bilkul pure Python -- koi JavaScript nahi.
    Internet chahiye Google Speech Recognition ke liye.
    """
    st.subheader("🎤 Voice Search — آواز سے تلاش")

    # Language choose karo
    lang_label = st.radio(
        "Bolo kis zubaan mein",
        ["English (en-US)", "Urdu — اردو (ur-PK)"],
        horizontal=True
    )

    # Language code nikaalo
    lang_code  = "en-US" if "English" in lang_label else "ur-PK"
    # Search direction bhi language pe depend karta hai
    search_dir = "eng"   if "English" in lang_label else "urdu"

    st.write("👇 **Microphone button dabao, clearly ek word bolo, phir roko.**")

    #    Microphone Input                                       
    # Yeh Streamlit ka native Python widget hai
    # Browser microphone access karta hai -- koi JS code nahi likhna pada
    audio = st.audio_input(
        "Microphone se record karein",
        label_visibility="collapsed"
    )

    st.divider()

    #    Kuch record nahi hua -> Word of the Day dikhao         
    if audio is None:
        wotd = db_random()
        if wotd:
            st.write("### 📖 Word of the Day — آج کا لفظ")
            show_word_full(wotd)
        return

    # Audio record hua — use text mein badlo
    st.audio(audio)  # jo record hua use dobara sunao

    with st.spinner("Awaaz samajh raha hoon…"):
        try:
            audio_bytes = audio.read()
            suna_gaya   = voice_to_text(audio_bytes, lang_code)

            st.success(f"✅ Suna: **{suna_gaya}**")
            st.write(f"### Results for: **{suna_gaya}**")
            st.divider()

            # Pehle exact match dhundho
            exact = db_get_one(suna_gaya)
            if exact:
                show_word_full(exact)
                # Milte-julte bhi dikhao
                others = [
                    r for r in db_search(suna_gaya, search_dir)
                    if r.Sr != exact.Sr
                ]
                if others:
                    st.write(f"**Milte-julte {len(others)} words:**")
                    for w in others[:10]:
                        show_word_card(w)
            else:
                # Partial search
                results = db_search(suna_gaya, search_dir)
                show_results(suna_gaya, results)

        except sr.UnknownValueError:
            # Awaaz capture hua lekin samajh nahi aaya
            st.error(
                "⚠️ Awaaz samajh nahi aayi.\n\n"
                "**Kya karein:**\n"
                "- Slowly aur clearly bolein\n"
                "- Microphone ke zyada paas bolein\n"
                "- Sirf ek word bolein (sentence nahi)\n"
                "- Background shor kam karein"
            )

        except sr.RequestError:
            # Internet nahi hai ya Google service down hai
            st.error(
                "⚠️ Speech recognition service se connect nahi hua.\n\n"
                "Internet connection check karein aur dobara koshish karein."
            )

        except Exception as e:
            st.error(f"⚠️ Kuch masla aaya: {e}")


# ==============================================================
# SECTION 11 -- PAGE: BROWSE
# ==============================================================

def page_browse():
    """
    Browse Page -- prefix se words dhundho.

    Saare words ko pehle 2-letter prefix ke hisaab se group karta hai.
    User prefix choose kare -> us prefix ke saare words list mein.

    Jaise:
    AB -> ab (399 words): ab, abacus, abandon, abbreviate ...
    AC -> ac (472 words): academic, accent, account, achieve ...
    """
    st.subheader("📂 Browse — الفاظ دیکھیں")

    # Prefix counts laao
    counts   = db_prefix_counts()
    prefixes = list(counts.keys())

    if not prefixes:
        st.warning("Database mein koi word nahi hai.")
        return

    # Dropdown -- prefix choose karo
    chosen = st.selectbox(
        "Prefix choose karein",
        options=prefixes,
        format_func=lambda p: f"{p.upper()}  --  {counts[p]} words"
    )

    words = db_by_prefix(chosen)

    st.write(f"### **{chosen.upper()}** -- {len(words)} words")
    st.divider()

    for word in words:
        show_word_card(word)


# ==============================================================
# SECTION 12 -- PAGE: FAVORITES
# ==============================================================

def page_favorites():
    """
    Favorites Page -- pasandida words.

    Sirf wo words dikhata hai jinhe user ne   favorite mark kiya hai.
    Favorites database mein save rehte hain -- app band hone par bhi.
    """
    st.subheader("⭐ Favorite Words — پسندیدہ الفاظ")

    favs = db_favorites()

    if not favs:
        st.info(
            "Abhi koi favorite nahi hai.\n\n"
            "Kisi bhi word ko dhundh kar **☆ Add to Favorites** dabao."
        )
        return

    st.success(f"**{len(favs)}** word(s) favorite mein hain.")
    st.divider()

    for word in favs:
        show_word_card(word)


# ==============================================================
# SECTION 13 -- PAGE: HISTORY
# ==============================================================

def page_history():
    """
    History Page -- is session mein jo words dekhe.

    Session memory mein rakhi jaati hai.
    Browser band karne par khud clear ho jaati hai.
    """
    st.subheader("🕐 History — حال کی تلاش")

    history = st.session_state.get("history", [])

    if not history:
        st.info("Abhi koi history nahi hai. Kuch words search karein.")
        return

    col_info, col_clear = st.columns([3, 1])
    with col_info:
        st.write(f"Is session mein **{len(history)}** word(s) dekhe.")
    with col_clear:
        if st.button("🗑️ Sab Clear Karein"):
            st.session_state["history"] = []
            st.rerun()

    st.divider()

    # Naye words pehle dikhao
    for eng in reversed(history):
        word = db_get_one(eng)
        if word:
            show_word_card(word)


# ==============================================================
# SECTION 14 -- SIDEBAR
# Left panel -- navigation aur stats
# ==============================================================

def build_sidebar() -> str:
    """
    Left sidebar banata hai.

    Dikhata hai:
    - App ka naam
    - Total words aur favorites ka count
    - Navigation menu
    - Haal ki searches (last 6)

    Return: user ne jo page choose kiya uska naam
    """
    with st.sidebar:
        st.title("📖 Dictionary")
        st.caption("English ↔ Urdu — انگریزی اردو لغت")
        st.divider()

        # Database stats
        db          = st.session_state.db
        total       = db.query(Word).count()
        fav_count   = db.query(Word).filter_by(is_favorite=True).count()

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Total Words", f"{total:,}")
        with col_b:
            st.metric("  Favorites", fav_count)

        st.divider()

        # Page navigation
        page = st.radio(
            "Navigation",
            [
                "  Text Search",
                "  Voice Search",
                "  Browse",
                "  Favorites",
                "  History",
            ],
            label_visibility="collapsed"
        )

        # Haal ki searches
        history = st.session_state.get("history", [])
        if history:
            st.divider()
            st.caption("Haal ki Searches:")
            for eng in reversed(history[-6:]):
                st.write(f"  {eng}")

    return page


# ==============================================================
# SECTION 15 -- MAIN (Entry Point)
# App shuru hone ka function
# ==============================================================

def main():
    """
    App ka entry point -- sabse pehle yahi function chalta hai.

    Steps:
    1. Streamlit page settings set karo
    2. Database se connect karo (ek baar -- cache use hota hai)
    3. Sidebar banao, user ka chosen page pata karo
    4. Page ka title dikhao
    5. User ke chosen page ka function call karo
    """
    # Step 1 -- Page settings
    st.set_page_config(
        page_title="English - Urdu Dictionary",
        page_icon=" ",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Step 2 -- Database connect karo
    # session_state mein rakhne se har rerun par dobara connect nahi hota
    if "db" not in st.session_state:
        st.session_state.db = db_connect()

    # Step 3 -- Sidebar + page selection
    chosen_page = build_sidebar()

    # Step 4 -- Page title
    db    = st.session_state.db
    total = db.query(Word).count()
    st.title("  English - Urdu Dictionary")
    st.caption(
        f"{total:,} words     انگریزی اردو لغت     "
        "Text Search   Voice Search   Favorites   Browse"
    )
    st.divider()

    # Step 5 -- Chosen page ka function call karo
    if   "Text Search"  in chosen_page:
        page_text_search()
    elif "Voice Search" in chosen_page:
        page_voice_search()
    elif "Browse"       in chosen_page:
        page_browse()
    elif "Favorites"    in chosen_page:
        page_favorites()
    elif "History"      in chosen_page:
        page_history()


# Jab yeh file directly run ho: python app.py ya streamlit run app.py
if __name__ == "__main__":
    main()
