# Mood → Spotify Playlist and Remix Finder

A Streamlit app that:
- Finds Spotify playlists by mood
- Finds official remixes/edits for a given track
- Uses Gemini to suggest a song from a mood and then finds remixes
- Includes a Diagnostics tab to verify API connectivity

## Prerequisites
- Python 3.9+ (recommended 3.10/3.11)
- A Spotify Developer application (Client ID and Client Secret)
- A Google AI Studio API key for Gemini
- Internet access

## Quick Start (Windows PowerShell)
```powershell
# 1) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -U streamlit spotipy google-genai

# 3) Set environment variables for this session (recommended)
$env:SPOTIPY_CLIENT_ID = "your_spotify_client_id"
$env:SPOTIPY_CLIENT_SECRET = "your_spotify_client_secret"
$env:GEMINI_API_KEY = "your_gemini_api_key"
# Optional: choose a Gemini model
$env:GEMINI_MODEL = "gemini-2.5-flash"

# 4) Run the app
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## Alternative: Streamlit Secrets
Instead of environment variables, you can store secrets. Create the file `.streamlit/secrets.toml` in the project root:

```toml
SPOTIPY_CLIENT_ID = "your_spotify_client_id"
SPOTIPY_CLIENT_SECRET = "your_spotify_client_secret"
GEMINI_API_KEY = "your_gemini_api_key"
# Optional
GEMINI_MODEL = "gemini-2.5-flash"
```

Then run the app normally:
```powershell
streamlit run app.py
```

## Features
- Mood → Playlist: Enter a mood (e.g., "chill") to find matching Spotify playlists
- Find Remixes: Provide "Track - Artist" or just the Track to find remixes/edits
- AI Mood → Remix: Enter a mood; Gemini suggests a song; app searches for remixes (limited to 6 results)
- Diagnostics: One-click connectivity checks for Gemini and Spotify

## Troubleshooting
- **Spotify invalid_client**:
  - Ensure `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` are correct
  - Verify the app exists in the Spotify Developer Dashboard
  - Make sure no placeholder values are used
- **Gemini client not initialized**:
  - Install the SDK: `pip install -U google-genai`
  - Set `GEMINI_API_KEY` (preferred) or `GOOGLE_API_KEY`
  - If a model error occurs, try setting `GEMINI_MODEL` to a model your key supports (e.g., `gemini-2.5-flash`)
- **No results**:
  - Try a broader query
  - For remixes, include the artist when possible for better precision

## Notes
- The app uses Spotify public Web API via Client Credentials flow (no user login)
- Audio is not generated or modified; only official Spotify content is searched and previewed
- The app avoids storing your keys; use env vars or Streamlit secrets

