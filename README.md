# dictionary
# 📖 English–Urdu Dictionary | انگریزی اردو لغت

A beautifully designed **English to Urdu dictionary** with voice search and text-to-speech, built with Python and Streamlit.

## Features

- 🔍 **Text Search** — Search all 2,093 words (ab → azygos)
- 🎤 **Voice Search** — Speak English or Urdu words (Chrome recommended)
- 🔊 **Text-to-Speech** — Hear English pronunciation + Urdu meaning
- 📂 **Browse by Prefix** — Browse words grouped by prefix (AB, AC, AD…AZ)
- 🕐 **Search History** — Recently viewed words
- 🖋️ **Jameel Noori Nastaleeq** — Classical Urdu typography
- ⚡ No external APIs — fully self-contained

## Run Locally

```bash
pip install streamlit
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path** to `app.py`
5. Click **Deploy**

No secrets or API keys needed — works out of the box.

## File Structure

```
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies (streamlit only)
├── .streamlit/
│   └── config.toml        # Server & theme configuration
├── data/
│   └── words.db           # SQLite database (2,093 words)
└── fonts/
    ├── Cataneo_BT.ttf     # English display font
    └── Jameel Noori Nastaleeq.ttf   # Urdu Nastaleeq font
```

## Database

- **2,093 English words** with Urdu meanings (A section: ab → azygos)
- Built-in SQLite — no database server required
- Source: Classical English-Urdu lexicon

## Voice Feature Notes

- Voice input uses the browser's **Web Speech API**
- Works best in **Google Chrome**
- Text-to-speech reads English word + Urdu meaning aloud
- Supports `en-US` (English) and `ur-PK` (Urdu) recognition
