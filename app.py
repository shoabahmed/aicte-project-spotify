import os
import streamlit as st

# Google Gemini (new google-genai client)
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except Exception:
    GEMINI_AVAILABLE = False

# Spotify via Spotipy
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except Exception:
    SPOTIPY_AVAILABLE = False

st.set_page_config(page_title="Mood → Spotify + Remix Finder", page_icon="🎧", layout="centered")
st.title("Mood → Spotify Playlist and Remix Finder 🎧")

# -------- Config / Secrets --------
# Safely read from st.secrets only if available; otherwise fall back.
def _get_secret_or_default(key: str, default: str) -> str:
    try:
        # Accessing st.secrets may raise if secrets file is missing
        return st.secrets[key]
    except Exception:
        return default

# Prefer environment variables, then st.secrets, then provided defaults
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID") or _get_secret_or_default("SPOTIPY_CLIENT_ID", "")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET") or _get_secret_or_default("SPOTIPY_CLIENT_SECRET", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or _get_secret_or_default("GOOGLE_API_KEY", "AIzaSyC3jlGZ0ig2I8BNamZgkvuf42lFNbmXINY")
# Prefer GEMINI_API_KEY (new var), fallback to GOOGLE_API_KEY
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or GOOGLE_API_KEY
# Allow overriding the Gemini model via env or secrets; default to a supported model
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL") or _get_secret_or_default("GEMINI_MODEL", "gemini-2.5-flash")

# -------- Helpers --------
@st.cache_resource(show_spinner=False)
def get_gemini_client():
    if not GEMINI_AVAILABLE:
        st.warning("google-genai is not installed. Please run `pip install -U google-genai`.")
        return None
    if not GEMINI_API_KEY:
        st.warning("GEMINI_API_KEY/GOOGLE_API_KEY not configured. Set it in env or st.secrets.")
        return None
    try:
        # The client picks up key from GEMINI_API_KEY env var
        os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
        return genai.Client()
    except Exception as e:
        st.error(f"Error initializing Gemini client: {e}")
        return None

@st.cache_data(show_spinner="Asking AI for a song suggestion...")
def get_song_from_mood(mood: str) -> tuple[str | None, str | None]:
    client = get_gemini_client()
    if not client:
        return None, None
    try:
        prompt = f"Suggest one song (track name and main artist) for the mood: '{mood}'. Respond only with 'Track Name - Artist Name'."
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0)
            ),
        )
        parts = (response.text or "").strip().split(' - ')
        if len(parts) >= 2:
            track = parts[0].strip()
            artist = " - ".join(parts[1:]).strip()
            return track, artist
        else:
            st.error(f"AI returned an unexpected format: {getattr(response, 'text', '')}")
            return None, None
    except Exception as e:
        st.error(f"Error with Gemini API: {e}")
        return None, None


@st.cache_resource(show_spinner=False)
def get_spotify_client():
    if not SPOTIPY_AVAILABLE:
        st.error("Spotipy is not installed. Please run `pip install spotipy`.")
        return None
    if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
        st.error("Spotify credentials missing. Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in env or secrets.")
        return None
    try:
        credentials = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
        return spotipy.Spotify(client_credentials_manager=credentials)
    except Exception as e:
        # Provide clearer hint for invalid_client responses
        msg = str(e)
        if "invalid_client" in msg:
            st.error("Spotify rejected the client credentials (invalid_client). Please verify SPOTIPY_CLIENT_ID/SECRET and that the app is created in the Spotify Dashboard.")
        else:
            st.error(f"Error initializing Spotify client: {e}")
        return None

# -------- Spotify Search --------
@st.cache_data(show_spinner="Searching Spotify...")
def search_spotify_playlists(query: str, limit: int = 10) -> list[dict]:
    client = get_spotify_client()
    if not client:
        return []
    try:
        # Spotipy does not expose search_playlists in newer versions; use the generic search API
        results = client.search(q=query, type="playlist", limit=limit)
        items = (results or {}).get("playlists", {}).get("items", []) or []
        safe = []
        for p in items:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            name = p.get("name")
            desc = p.get("description") if isinstance(p.get("description"), str) else None
            images = p.get("images") or []
            image_url = None
            if isinstance(images, list) and images:
                first = images[0] or {}
                if isinstance(first, dict):
                    image_url = first.get("url")
            if pid and name:
                safe.append({"id": pid, "name": name, "description": desc, "image": image_url})
        return safe
    except Exception as e:
        st.error(f"Error searching Spotify playlists: {e}")
        return []

@st.cache_data(show_spinner="Searching Spotify...")
def search_remixes(track: str, artist: str, limit: int = 10) -> list[dict]:
    client = get_spotify_client()
    if not client:
        return []
    try:
        query = f"remix {track} {artist}"
        # Use generic search for tracks
        results = client.search(q=query, type="track", limit=limit)
        return [{"id": t["id"], "name": t["name"], "artists": ", ".join([a["name"] for a in t.get("artists", [])]), "url": t.get("external_urls", {}).get("spotify"), "preview": t.get("preview_url"), "image": t.get("album", {}).get("images", [{}])[0].get("url") if t.get("album", {}).get("images") else None} for t in results.get("tracks", {}).get("items", [])]
    except Exception as e:
        st.error(f"Error searching remixes: {e}")
        return []

def parse_track_artist(input_text: str) -> tuple[str | None, str | None]:
    # Accept 'Track - Artist', 'Track-Artist', or just 'Track'
    if not input_text:
        return None, None
    text = input_text.strip()
    if ' - ' in text:
        parts = text.split(' - ', 1)
    elif '-' in text:
        parts = text.split('-', 1)
    else:
        # Track only
        return text if text else None, None
    track = parts[0].strip()
    artist = parts[1].strip() if len(parts) > 1 else None
    if not track:
        return None, artist if artist else None
    return track, artist if artist else None

@st.cache_data(show_spinner="Searching Spotify...")
def search_original_track(track: str, artist: str, limit: int = 10) -> list[dict]:
    client = get_spotify_client()
    if not client:
        return []
    try:
        query = f"track:{track} artist:{artist}"
        results = client.search(q=query, type="track", limit=limit)
        return [{"id": t["id"], "name": t["name"], "artists": ", ".join([a["name"] for a in t.get("artists", [])]), "url": t.get("external_urls", {}).get("spotify"), "preview": t.get("preview_url"), "image": t.get("album", {}).get("images", [{}])[0].get("url") if t.get("album", {}).get("images") else None} for t in results.get("tracks", {}).get("items", [])]
    except Exception as e:
        st.error(f"Error searching original tracks: {e}")
        return []

# -------- Embeds --------
def embed_playlist(playlist_id: str, height: int = 300):
    st.components.v1.iframe(f"https://open.spotify.com/embed/playlist/{playlist_id}", height=height)

def embed_track(track_id: str, height: int = 152):
    st.components.v1.iframe(f"https://open.spotify.com/embed/track/{track_id}", height=height)

# -------- Diagnostics --------
@st.cache_data(show_spinner=False)
def check_gemini_connectivity() -> dict:
    client = get_gemini_client()
    if not client:
        # Surface available models for easier debugging
        available = []
        try:
            os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY or ""
            client_tmp = genai.Client()
            for m in client_tmp.models.list():
                available.append(getattr(m, "name", ""))
        except Exception:
            pass
        hint = f" Available models: {', '.join(available[:10])}..." if available else ""
        return {"ok": False, "error": "Gemini client not initialized." + hint}
    try:
        resp = client.models.generate_content(model=GEMINI_MODEL_NAME, contents="ping")
        ok = bool(getattr(resp, "text", ""))
        return {"ok": ok, "error": None if ok else "Empty response"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@st.cache_data(show_spinner=False)
def check_spotify_connectivity() -> dict:
    client = get_spotify_client()
    if not client:
        return {"ok": False, "error": "Spotify client not initialized"}
    try:
        # Minimal search on a common term
        results = client.search(q="test", type="track", limit=1)
        ok = bool((results or {}).get("tracks", {}).get("items"))
        return {"ok": ok, "error": None if ok else "No items returned"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# -------- UI --------
tab1, tab2, tab3, tab4 = st.tabs(["Mood → Playlist", "Find Remixes", "✨ AI Mood → Remix", "Diagnostics"])

with tab1:
    st.subheader("Find a playlist by mood")
    mood = st.text_input("Enter a mood (e.g., 'chill', 'happy', 'sad')", key="mood_input")
    if st.button("Find Playlist"):
        if not mood.strip():
            st.warning("Please enter a mood.")
        else:
            with st.spinner(f"Searching for playlists that match the mood: '{mood}'..."):
                playlists = search_spotify_playlists(mood)
            if not playlists:
                st.info("No playlists found for the given mood.")
            else:
                for p in playlists:
                    cols = st.columns([1, 3])
                    with cols[0]:
                        if p["image"]:
                            st.image(p["image"], use_container_width=True)
                    with cols[1]:
                        st.markdown(f"**{p['name']}**")
                        st.write(p["description"] or "No description available.")
                        if p["id"]:
                            embed_playlist(p["id"])

with tab2:
    st.subheader("Toggle to find remixes on Spotify")
    st.caption("Search for official remix/alt versions like 'Club Mix', 'Extended Mix', 'Radio Edit', etc.")
    remix_mode = st.radio("Select remix mode:", ("Find Remixes", "Find Original"))
    track_artist = st.text_input("Enter track and artist (e.g., 'Blinding Lights - The Weeknd')", key="track_artist")
    if st.button("Search Remix"):
        if not track_artist.strip():
            st.warning("Please enter a track and artist.")
        else:
            with st.spinner(f"Searching for {'original' if remix_mode == 'Find Original' else 'remix'} version of the track..."):
                track_name, artist_name = parse_track_artist(track_artist)
                if not track_name and not artist_name:
                    st.error("Please enter at least a track name.")
                    remixes = []
                else:
                    if remix_mode == "Find Remixes":
                        # If artist is missing, search with track only
                        remixes = search_remixes(track_name or "", artist_name or "", limit=10)
                    else:
                        # For original, search with available fields
                        if track_name and artist_name:
                            remixes = search_original_track(track_name, artist_name, limit=10)
                        else:
                            # Fallback: search track-only
                            remixes = search_original_track(track_name or "", "", limit=10)
            if not remixes:
                st.info(f"No {'remixes' if remix_mode == 'Find Remixes' else 'original track'} found for the given input.")
            else:
                for r in remixes:
                    cols = st.columns([1, 3])
                    with cols[0]:
                        if r["image"]:
                            st.image(r["image"], use_container_width=True)
                    with cols[1]:
                        st.markdown(f"**{r['name']}**")
                        st.write(r["artists"])
                        if r["url"]:
                            st.markdown(f"[Open in Spotify]({r['url']})")
                        if r["preview"]:
                            st.audio(r["preview"])
                        if r["id"]:
                            embed_track(r["id"])

with tab3:
    st.subheader("Find Remixes with an AI Song Suggestion")
    st.caption("1. Enter a mood. 2. Let AI suggest a song. 3. Find remixes for that song.")
    ai_mood = st.text_input("Enter a mood (e.g., 'a hopeful morning after a storm')", key="ai_mood")

    if st.button("Get AI Suggestion & Find Remixes"):
        if not ai_mood.strip():
            st.warning("Please enter a mood.")
        elif not get_gemini_client():
             st.warning("Gemini AI is not configured. Please check your API key.")
        else:
            track, artist = get_song_from_mood(ai_mood)
            if track and artist:
                st.success(f"AI suggested: **{track}** by **{artist}**")
                st.write("Now searching for remixes...")
                remixes = search_remixes(track, artist, limit=6)
                if not remixes:
                    st.info("No remixes found for the suggested track.")
                else:
                    for r in remixes:
                        cols = st.columns([1, 3])
                        with cols[0]:
                            if r["image"]:
                                st.image(r["image"], use_container_width=True)
                        with cols[1]:
                            st.markdown(f"**{r['name']}**")
                            st.write(r["artists"])
                            if r["url"]:
                                st.markdown(f"[Open in Spotify]({r['url']})")
                            if r["preview"]:
                                st.audio(r["preview"])
                            if r["id"]:
                                embed_track(r["id"])
            else:
                st.error("Could not get a song suggestion from the AI. Please try a different mood.")


with st.expander("Setup notes"):
    st.markdown("""
- This app does not generate or remix audio. It only searches Spotify for mood-based playlists and remix versions.
- You need API credentials for both Spotify and Google:
  - `SPOTIPY_CLIENT_ID`
  - `SPOTIPY_CLIENT_SECRET`
  - `GOOGLE_API_KEY`
- Add them as environment variables or in `.streamlit/secrets.toml`.
- If embeds don't load, click the 'Open in Spotify' link.
""")

with tab4:
    st.subheader("Diagnostics")
    st.caption("Run quick connectivity checks for Gemini and Spotify.")
    if st.button("Run Checks"):
        with st.spinner("Checking APIs..."):
            gem = check_gemini_connectivity()
            spo = check_spotify_connectivity()
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**Gemini**")
            if gem.get("ok"):
                st.success("OK")
            else:
                st.error(f"Failed: {gem.get('error')}")
        with colB:
            st.markdown("**Spotify**")
            if spo.get("ok"):
                st.success("OK")
            else:
                st.error(f"Failed: {spo.get('error')}")
