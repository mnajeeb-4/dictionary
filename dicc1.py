import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# Core Database Imports
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# External Feature Libraries (Wrapped in safe check/try blocks)
import pyttsx3

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None


# ==========================================
# 1. DATABASE SETUP & OBJECT MODEL (ORM)
# ==========================================

Base = declarative_base()

class Word(Base):
    """
    Blueprint representing the 'words' table inside the SQLite Database.
    """
    __tablename__ = 'words'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    english_word = Column(String, unique=True, nullable=False)
    urdu_meaning = Column(String, nullable=False)
    is_favorite = Column(Boolean, default=False)


def initialize_database():
    """
    Sets up the SQLite database connection, builds the schema, and returns a session object.
    Also handles conditional imports from data files if the database is newly created.
    """
    # Create an engine to connect to 'dictionary.db' locally
    engine = create_engine('sqlite:///dictionary.db', echo=False)
    
    # Generate the table schemas if they do not exist
    Base.metadata.create_all(engine)
    
    # Establish local Session maker and instantiate a session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # If the database is completely empty, look for data.xlsx or data.pdf to populate it
    if session.query(Word).count() == 0:
        extract_and_populate_data(session)
        
    return session


# ==========================================
# 2. FILE DATA EXTRACTION LOGIC
# ==========================================

def extract_and_populate_data(session):
    """
    Attempts to look for 'data.xlsx' and 'data.pdf' to extract words dynamically.
    If neither file is found, it injects sample words so the app is instantly usable.
    """
    data_imported = False

    # A. Pandas Excel Extraction Strategy
    if os.path.exists('data.xlsx') and pd is not None:
        try:
            df = pd.read_excel('data.xlsx')
            # Normalize column looks to find proper keywords flexibly
            eng_col, urdu_col = None, None
            for col in df.columns:
                if str(col).lower() in ['english_word', 'words', 'word', 'english']:
                    eng_col = col
                if str(col).lower() in ['urdu_meaning', 'meaning', 'meanings', 'urdu']:
                    urdu_col = col

            if eng_col and urdu_col:
                for _, row in df.iterrows():
                    eng = str(row[eng_col]).strip()
                    urdu = str(row[urdu_col]).strip()
                    if eng and urdu and not pd.isna(row[eng_col]) and not pd.isna(row[urdu_col]):
                        # Double check for entry collisions
                        if not session.query(Word).filter_by(english_word=eng).first():
                            session.add(Word(english_word=eng, urdu_meaning=urdu))
                session.commit()
                data_imported = True
        except Exception as e:
            print(f"[Extractor] Error reading Excel data.xlsx: {e}")

    # B. PyPDF2 Parsing Strategy 
    if os.path.exists('data.pdf') and PyPDF2 is not None and not data_imported:
        try:
            with open('data.pdf', 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        # Assumes formatting structure like "Word : Meaning" or "Word - Meaning" per line
                        for line in text.split('\n'):
                            delimiter = ':' if ':' in line else ('-' if '-' in line else None)
                            if delimiter:
                                parts = line.split(delimiter, 1)
                                eng, urdu = parts[0].strip(), parts[1].strip()
                                if eng and urdu:
                                    if not session.query(Word).filter_by(english_word=eng).first():
                                        session.add(Word(english_word=eng, urdu_meaning=urdu))
                session.commit()
                data_imported = True
        except Exception as e:
            print(f"[Extractor] Error processing PDF data.pdf: {e}")

    # C. Fallback Core Dataset (Ensures functionality right away)
    if session.query(Word).count() == 0:
        fallback_data = [
            ("apple", "سیب", False),
            ("book", "کتاب", False),
            ("computer", "کمپیوٹر", False),
            ("cat", "بلی", True),
            ("water", "پانی", False),
            ("beautiful", "خوبصورت", False),
            ("knowledge", "علم", True),
            ("software", "سافٹ ویئر", False)
        ]
        for eng, urdu, fav in fallback_data:
            session.add(Word(english_word=eng, urdu_meaning=urdu, is_favorite=fav))
        session.commit()


# ==========================================
# 3. INTERACTIVE USER INTERFACE LAYER
# ==========================================

class DictionaryApp:
    def __init__(self, root, db_session):
        self.root = root
        self.session = db_session
        self.selected_word = None
        self.current_words_list = []  # Tracks currently displayed elements to map index selections directly

        # Initialize window parameters
        self.root.title("Modern English-Urdu Dictionary")
        self.root.geometry("850x550")
        self.root.set_window_icon = None
        
        # Configure overall themes and widget styles using TTK
        self.setup_styles()
        
        # Construct layout containers
        self.build_ui_layout()
        
        # Pull records immediately on launch
        self.filter_and_refresh_list()

    def setup_styles(self):
        """ Configures color schemes and modern fonts for the components. """
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Primary application palette colors
        self.bg_light = "#f8f9fa"
        self.bg_white = "#ffffff"
        self.primary_blue = "#2b5797"
        self.text_dark = "#2c3e50"
        
        self.root.configure(bg=self.bg_light)
        
        self.style.configure("TFrame", background=self.bg_light)
        self.style.configure("Card.TFrame", background=self.bg_white, relief="flat")
        
        # Custom button styles
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
        self.style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), background=self.primary_blue, foreground="white")
        self.style.map("Action.TButton", background=[('active', '#1e3d6b')])

        # Label configurations
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), background=self.bg_light, foreground=self.text_dark)
        self.style.configure("DetailTitle.TLabel", font=("Segoe UI", 26, "bold"), background=self.bg_white, foreground=self.primary_blue)
        self.style.configure("DetailUrdu.TLabel", font=("Segoe UI", 22), background=self.bg_white, foreground="#27ae60")

    def build_ui_layout(self):
        """ Assembles side panel search structures and content view components. """
        # Main structure breakdown: Left panel (Search & List) vs Right panel (Details display)
        left_pane = ttk.Frame(self.root, padding=15, style="TFrame")
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, minsize=320)
        
        right_pane = ttk.Frame(self.root, padding=15, style="TFrame")
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # ----------------- LEFT PANE: CONTROLS -----------------
        lbl_search = ttk.Label(left_pane, text="Dictionary Search Engine", style="Header.TLabel")
        lbl_search.pack(anchor=tk.W, pady=(0, 10))

        # Dynamic search input tracking string modifications
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_and_refresh_list())
        
        self.search_entry = ttk.Entry(left_pane, textvariable=self.search_var, font=("Segoe UI", 11))
        self.search_entry.pack(fill=tk.X, pady=(0, 8))
        self.search_entry.focus() # Target cursor input focus on startup

        # Radio button selection to toggle Search Orientations
        self.search_mode = tk.StringVar(value="ENG")
        mode_frame = ttk.Frame(left_pane)
        mode_frame.pack(fill=tk.X, pady=(0, 5))
        
        rb_eng = ttk.Radiobutton(mode_frame, text="English → Urdu", variable=self.search_mode, value="ENG", command=self.filter_and_refresh_list)
        rb_eng.pack(side=tk.LEFT, padx=(0, 15))
        
        rb_urdu = ttk.Radiobutton(mode_frame, text="Urdu → English", variable=self.search_mode, value="URDU", command=self.filter_and_refresh_list)
        rb_urdu.pack(side=tk.LEFT)

        # Favorite records filter toggle status
        self.filter_favorites_var = tk.BooleanVar(value=False)
        chk_fav = ttk.Checkbutton(left_pane, text="⭐ Show Favorites Only", variable=self.filter_favorites_var, command=self.filter_and_refresh_list)
        chk_fav.pack(anchor=tk.W, pady=(0, 10))

        # Scrollable listbox wrapper frame
        list_frame = ttk.Frame(left_pane)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scroll_bar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.word_listbox = tk.Listbox(
            list_frame, 
            vertical_scrollbar=scroll_bar, 
            font=("Segoe UI", 11), 
            bd=1, 
            relief="solid", 
            highlightthickness=0,
            selectbackground=self.primary_blue,
            selectforeground="white"
        )
        
        scroll_bar.config(command=self.word_listbox.yview)
        self.word_listbox.config(yscrollcommand=scroll_bar.set)
        
        scroll_bar.pack(side=tk.RIGHT, fill=tk.Y)
        self.word_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Link listbox click selection event listener
        self.word_listbox.bind("<<ListboxSelect>>", self.on_listbox_item_selected)

        # ----------------- RIGHT PANE: DETAIL VIEW -----------------
        # Wrap everything in a card-like stylized white background display block
        card_view = ttk.Frame(right_pane, padding=30, style="Card.TFrame")
        card_view.pack(fill=tk.BOTH, expand=True)

        # Placeholder message inside layout
        self.lbl_no_selection = ttk.Label(card_view, text="Select a word from the list to view its properties.", font=("Segoe UI", 12, "italic"), background=self.bg_white, foreground="gray")
        self.lbl_no_selection.pack(expand=True)

        # Detail structures (hidden on app boot up until item selected)
        self.detail_container = ttk.Frame(card_view, style="Card.TFrame")
        
        self.lbl_english = ttk.Label(self.detail_container, text="Word", style="DetailTitle.TLabel")
        self.lbl_english.pack(anchor=tk.W, pady=(0, 5))
        
        self.lbl_divider = tk.Frame(self.detail_container, height=2, bg=self.bg_light)
        self.lbl_divider.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(self.detail_container, text="Meaning / ترجمہ :", font=("Segoe UI", 11, "bold"), background=self.bg_white, foreground="gray").pack(anchor=tk.W)
        
        # Anchor reading direction to the right side for classic Urdu formatting style
        self.lbl_urdu = ttk.Label(self.detail_container, text="معنی", style="DetailUrdu.TLabel", anchor=tk.E)
        self.lbl_urdu.pack(fill=tk.X, pady=(5, 30))

        # Bottom row interactions segment
        btn_row = ttk.Frame(self.detail_container, style="Card.TFrame")
        btn_row.pack(anchor=tk.W, pady=(10, 0))

        self.btn_speak = ttk.Button(btn_row, text="🔊 Audio Pronounce", style="Action.TButton", command=self.pronounce_english_word)
        self.btn_speak.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_fav_toggle = ttk.Button(btn_row, text="⭐ Add to Favorites", command=self.toggle_favorite_status)
        self.btn_fav_toggle.pack(side=tk.LEFT)

    # ==========================================
    # 4. INTERACTIVE USER LOGIC CONTROLLERS
    # ==========================================

    def filter_and_refresh_list(self):
        """
        Queries the internal SQLite database applying user filters, text constraints, 
        and updates the graphical listbox contents gracefully.
        """
        search_query = self.search_var.get().strip()
        mode = self.search_mode.get()
        only_favs = self.filter_favorites_var.get()

        # Build basic query block
        db_query = self.session.query(Word)

        if only_favs:
            db_query = db_query.filter(Word.is_favorite == True)

        if search_query:
            if mode == "ENG":
                db_query = db_query.filter(Word.english_word.like(f"%{search_query}%"))
            else:
                db_query = db_query.filter(Word.urdu_meaning.like(f"%{search_query}%"))

        # Alphabetize presentation order according to language lookup modes
        if mode == "ENG":
            db_query = db_query.order_by(Word.english_word.asc())
        else:
            db_query = db_query.order_by(Word.urdu_meaning.asc())

        # Cache query output to map selections securely
        self.current_words_list = db_query.all()

        # Re-render visual list elements
        self.word_listbox.delete(0, tk.END)
        for w in self.current_words_list:
            star_indicator = " ⭐" if w.is_favorite else ""
            if mode == "ENG":
                display_string = f"{w.english_word}{star_indicator}"
            else:
                display_string = f"{w.urdu_meaning}{star_indicator}"
            self.word_listbox.insert(tk.END, display_string)

    def on_listbox_item_selected(self, event):
        """ Triggers whenever user picks a row index from the list. """
        selected_indices = self.word_listbox.curselection()
        if not selected_indices:
            return
        
        target_index = selected_indices[0]
        if target_index < len(self.current_words_list):
            self.selected_word = self.current_words_list[target_index]
            self.render_word_details()

    def render_word_details(self):
        """ Displaces context placeholders and draws full specific data into the cards view. """
        self.lbl_no_selection.pack_forget()  # Hide empty state message
        self.detail_container.pack(fill=tk.BOTH, expand=True)  # Disclose real details view frame

        self.lbl_english.config(text=self.selected_word.english_word)
        self.lbl_urdu.config(text=self.selected_word.urdu_meaning)

        # Dynamically switch context configurations on the Favorites toggle button setup
        if self.selected_word.is_favorite:
            self.btn_fav_toggle.config(text="❌ Remove Favorite")
        else:
            self.btn_fav_toggle.config(text="⭐ Add to Favorites")

    def toggle_favorite_status(self):
        """ Swaps favorite status flags inside database schema models securely. """
        if not self.selected_word:
            return

        # Flip the state
        self.selected_word.is_favorite = not self.selected_word.is_favorite
        self.session.commit()

        # Update view items
        self.render_word_details()
        
        # Save positional indexes to restore scroll position and highlight state seamlessly
        current_index = self.word_listbox.curselection()
        self.filter_and_refresh_list()
        
        if current_index:
            self.word_listbox.selection_set(current_index[0])
            self.word_listbox.see(current_index[0])

    def pronounce_english_word(self):
        """ Uses pyttsx3 safely wrapped inside a backend thread to block interface freezing. """
        if not self.selected_word:
            return
        
        text_to_say = self.selected_word.english_word

        def tts_worker_thread():
            try:
                # Local thread instantiation guarantees stable runtime context cycles across systems
                engine = pyttsx3.init()
                engine.say(text_to_say)
                engine.runAndWait()
            except Exception as ex:
                print(f"[TTS Engine Error]: {ex}")

        # Dispatch background worker task group
        threading.Thread(target=tts_worker_thread, daemon=True).start()


# ==========================================
# 5. MAIN EXECUTION ROUTINE ENTRY POINT
# ==========================================

if __name__ == "__main__":
    # Create database transaction layer context manager structure
    db_session = initialize_database()
    
    # Establish root display window instance context loop handles
    root_window = tk.Tk()
    
    # Fire up user desktop application interface wrapper instances
    app = DictionaryApp(root_window, db_session)
    
    # Pass event cycles onto standard loop tracking systems
    root_window.mainloop()
