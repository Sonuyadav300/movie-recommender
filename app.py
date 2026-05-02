import requests
import streamlit as st
import random

# =============================
# CONFIG
# =============================
API_BASE = "http://localhost:8000"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

st.set_page_config(page_title="MoodFlix - Movie Recommender", page_icon="🎬", layout="wide")

# =============================
# MOOD CONFIGURATION
# =============================
MOOD_CONFIG = {
    "Happy": {
        "emoji": "😊",
        "name": "Happy",
        "description": "Feel-good comedies and uplifting stories",
        "color": "#FFD700",
    },
    "Sad": {
        "emoji": "😢",
        "name": "Sad",
        "description": "Emotional dramas and tearjerkers",
        "color": "#6495ED",
    },
    "Scared": {
        "emoji": "😱",
        "name": "Scared",
        "description": "Horror and spine-chilling thrillers",
        "color": "#8B0000",
    },
    "Excited": {
        "emoji": "🤩",
        "name": "Excited",
        "description": "Action-packed adventures",
        "color": "#FF4500",
    },
    "Romantic": {
        "emoji": "💕",
        "name": "Romantic",
        "description": "Love stories and romantic comedies",
        "color": "#FF69B4",
    },
    "Thoughtful": {
        "emoji": "🤔",
        "name": "Thoughtful",
        "description": "Mind-bending mysteries and thrillers",
        "color": "#9370DB",
    },
    "Relaxed": {
        "emoji": "😌",
        "name": "Relaxed",
        "description": "Light-hearted and easy watching",
        "color": "#98FB98",
    },
    "Adventurous": {
        "emoji": "🚀",
        "name": "Adventurous",
        "description": "Epic journeys and fantasy worlds",
        "color": "#00CED1",
    },
    "Funny": {
        "emoji": "😂",
        "name": "Funny",
        "description": "Laugh-out-loud comedies",
        "color": "#FFA500",
    },
    "Motivated": {
        "emoji": "💪",
        "name": "Motivated",
        "description": "Inspiring true stories and sports dramas",
        "color": "#32CD32",
    },
    "Family": {
        "emoji": "👨‍👩‍👧‍👦",
        "name": "Family",
        "description": "Fun for the whole family",
        "color": "#87CEEB",
    },
    "Mysterious": {
        "emoji": "🔮",
        "name": "Mysterious",
        "description": "Crime and detective stories",
        "color": "#4B0082",
    },
}

# =============================
# STYLES
# =============================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    .movie-title {
        font-size: 0.9rem;
        line-height: 1.15rem;
        height: 2.3rem;
        overflow: hidden;
        text-align: center;
        font-weight: 500;
        margin-top: 8px;
    }
    .stImage > img {
        border-radius: 12px;
        transition: transform 0.3s ease;
    }
    .stImage > img:hover {
        transform: scale(1.02);
    }
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# =============================
# SESSION STATE
# =============================
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"
if "selected_tmdb_id" not in st.session_state:
    st.session_state.selected_tmdb_id = None
if "selected_mood" not in st.session_state:
    st.session_state.selected_mood = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

# =============================
# URL QUERY PARAMS
# =============================
qp_page = st.query_params.get("page")
qp_id = st.query_params.get("id")
qp_mood = st.query_params.get("mood")

if qp_page in ("home", "moods", "mood_results", "details"):
    st.session_state.current_page = qp_page
if qp_id:
    try:
        st.session_state.selected_tmdb_id = int(qp_id)
        st.session_state.current_page = "details"
    except:
        pass
if qp_mood:
    st.session_state.selected_mood = qp_mood
    st.session_state.current_page = "mood_results"

# =============================
# NAVIGATION
# =============================
def goto_home():
    st.session_state.current_page = "home"
    st.session_state.selected_mood = None
    st.session_state.search_query = ""
    st.query_params.clear()
    st.query_params["page"] = "home"
    st.rerun()

def goto_moods_page():
    st.session_state.current_page = "moods"
    st.query_params.clear()
    st.query_params["page"] = "moods"
    st.rerun()

def goto_mood_results(mood: str):
    st.session_state.current_page = "mood_results"
    st.session_state.selected_mood = mood
    st.query_params.clear()
    st.query_params["page"] = "mood_results"
    st.query_params["mood"] = mood
    st.rerun()

def goto_details(tmdb_id: int):
    st.session_state.current_page = "details"
    st.session_state.selected_tmdb_id = int(tmdb_id)
    st.query_params.clear()
    st.query_params["page"] = "details"
    st.query_params["id"] = str(int(tmdb_id))
    st.rerun()

# =============================
# API HELPER
# =============================
@st.cache_data(ttl=60)
def api_get_json(path: str, params: dict | None = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except requests.exceptions.ConnectionError:
        return None, "Connection error."
    except Exception as e:
        return None, f"Request failed: {e}"

# =============================
# UI COMPONENTS
# =============================
def poster_grid(cards, cols=5, key_prefix="grid"):
    if not cards:
        st.info("No movies to show.")
        return

    rows = (len(cards) + cols - 1) // cols
    idx = 0

    for r in range(rows):
        colset = st.columns(cols)
        for c in range(cols):
            if idx >= len(cards):
                break
            m = cards[idx]
            idx += 1

            tmdb_id = m.get("tmdb_id")
            title = m.get("title", "Untitled")
            poster = m.get("poster_url")
            year = (m.get("release_date") or "")[:4]
            vote_avg = m.get("vote_average")

            with colset[c]:
                if poster:
                    st.image(poster, use_container_width=True)
                else:
                    st.markdown(
                        """
                        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    height: 280px; display: flex; align-items: center; 
                                    justify-content: center; border-radius: 12px;">
                            <span style="font-size: 3rem;">🎬</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                if st.button("▶ View", key=f"{key_prefix}_{r}_{c}_{idx}_{tmdb_id}", use_container_width=True):
                    if tmdb_id:
                        goto_details(tmdb_id)

                st.markdown(f"<div class='movie-title'>{title}</div>", unsafe_allow_html=True)

                info_parts = []
                if year:
                    info_parts.append(year)
                if vote_avg:
                    info_parts.append(f"⭐ {vote_avg:.1f}")
                if info_parts:
                    st.markdown(
                        f"<div style='text-align:center; color:#888; font-size:0.75rem;'>{' • '.join(info_parts)}</div>",
                        unsafe_allow_html=True
                    )

def render_mood_grid(key_suffix=""):
    mood_list = list(MOOD_CONFIG.values())
    cols_per_row = 4

    for i in range(0, len(mood_list), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(mood_list):
                mood = mood_list[i + j]
                with col:
                    btn_label = f"{mood['emoji']} {mood['name']}"
                    if st.button(
                        btn_label,
                        key=f"mood_{mood['name']}{key_suffix}{i}_{j}",
                        use_container_width=True,
                        help=mood['description']
                    ):
                        goto_mood_results(mood['name'])

def to_cards_from_tfidf_items(tfidf_items):
    cards = []
    for x in tfidf_items or []:
        tmdb = x.get("tmdb") or {}
        if tmdb.get("tmdb_id"):
            cards.append({
                "tmdb_id": tmdb["tmdb_id"],
                "title": tmdb.get("title") or x.get("title") or "Untitled",
                "poster_url": tmdb.get("poster_url"),
                "release_date": tmdb.get("release_date"),
            })
    return cards

def parse_tmdb_search_to_cards(data, keyword: str, limit: int = 24):
    keyword_l = keyword.strip().lower()

    if isinstance(data, dict) and "results" in data:
        raw = data.get("results") or []
        raw_items = []
        for m in raw:
            title = (m.get("title") or "").strip()
            tmdb_id = m.get("id")
            poster_path = m.get("poster_path")
            if not title or not tmdb_id:
                continue
            raw_items.append({
                "tmdb_id": int(tmdb_id),
                "title": title,
                "poster_url": f"{TMDB_IMG}{poster_path}" if poster_path else None,
                "release_date": m.get("release_date", ""),
            })
    elif isinstance(data, list):
        raw_items = []
        for m in data:
            tmdb_id = m.get("tmdb_id") or m.get("id")
            title = (m.get("title") or "").strip()
            poster_url = m.get("poster_url")
            if not title or not tmdb_id:
                continue
            raw_items.append({
                "tmdb_id": int(tmdb_id),
                "title": title,
                "poster_url": poster_url,
                "release_date": m.get("release_date", ""),
            })
    else:
        return [], []

    matched = [x for x in raw_items if keyword_l in x["title"].lower()]
    final_list = matched if matched else raw_items

    suggestions = []
    for x in final_list[:10]:
        year = (x.get("release_date") or "")[:4]
        label = f"{x['title']} ({year})" if year else x["title"]
        suggestions.append((label, x["tmdb_id"]))

    cards = [
        {
            "tmdb_id": x["tmdb_id"],
            "title": x["title"],
            "poster_url": x["poster_url"],
            "release_date": x.get("release_date")
        }
        for x in final_list[:limit]
    ]

    return suggestions, cards

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## 🎬 Menu")
    st.markdown("---")

    if st.button("🏠 Home", use_container_width=True):
        goto_home()

    if st.button("🎭 Mood Picks", use_container_width=True):
        goto_moods_page()

    st.markdown("---")

    st.markdown("### 📂 Browse Categories")
    home_category = st.selectbox(
        "Category",
        ["trending", "popular", "top_rated", "now_playing", "upcoming"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("---")

    st.markdown("### ⚙️ Display Settings")
    grid_cols = st.slider("Grid columns", 3, 8, 5)

    st.markdown("---")

# =============================
# MAIN HEADER
# =============================
st.markdown(
    """
    <div style="text-align: center; padding: 20px 0;">
        <h1 style="font-size: 2.8rem; margin-bottom: 5px; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            🎬 MoodFlix
        </h1>
        <p style="color: #666; font-size: 1.1rem;">
            AI Based Movie Recommendations System
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
st.divider()

# ==========================================================
# PAGE: HOME
# ==========================================================
if st.session_state.current_page == "home":

    st.markdown("### 🔍 Search Movies")

    col1, col2 = st.columns([5, 1])
    with col1:
        typed = st.text_input(
            "Search",
            value=st.session_state.search_query,
            placeholder="Type movie name: Avengers, Batman, Inception, Hulk...",
            label_visibility="collapsed"
        )
        st.session_state.search_query = typed

    with col2:
        search_btn = st.button("🔍", use_container_width=True)

    if typed.strip():
        if len(typed.strip()) < 2:
            st.caption("⚠️ Type at least 2 characters to search.")
        else:
            with st.spinner("🔍 Searching..."):
                data, err = api_get_json("/tmdb/search", params={"query": typed.strip()})

                if err or data is None:
                    st.error(f"❌ Search failed: {err}")
                else:
                    suggestions, cards = parse_tmdb_search_to_cards(data, typed.strip(), limit=24)

                    if suggestions:
                        st.markdown("#### 💡 Quick Select")
                        labels = ["-- Select a movie --"] + [s[0] for s in suggestions]
                        selected = st.selectbox(
                            "Suggestions",
                            labels,
                            index=0,
                            label_visibility="collapsed"
                        )
                        if selected != "-- Select a movie --":
                            label_to_id = {s[0]: s[1] for s in suggestions}
                            goto_details(label_to_id[selected])

                    if cards:
                        st.markdown(f"### 🎯 Search Results ({len(cards)} movies found)")
                        poster_grid(cards, cols=grid_cols, key_prefix="search_results")
                    else:
                        st.info("No movies found. Try a different search term.")

        st.stop()
    st.divider()

    category_display = home_category.replace('_', ' ').title()
    st.markdown(f"### 🏠 {category_display} Movies")

    with st.spinner(f"Loading {category_display.lower()} movies..."):
        home_cards, err = api_get_json(
            "/home", params={"category": home_category, "limit": 24}
        )

    if err or not home_cards:
        st.error(f"❌ Failed to load movies: {err or 'Unknown error'}")
        st.stop()

    poster_grid(home_cards, cols=grid_cols, key_prefix="home_feed")

# ==========================================================
# PAGE: MOOD SELECTION
# ==========================================================
elif st.session_state.current_page == "moods":

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Home", use_container_width=True):
            goto_home()

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 30px; border-radius: 20px; margin: 20px 0; text-align: center;">
            <h2 style="color: white; margin-bottom: 10px; font-size: 2rem;">
                🎭 Choose Your Mood
            </h2>
            <p style="color: rgba(255,255,255,0.9); font-size: 1.1rem;">
                How are you feeling? Select a mood to get personalized movie recommendations!
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### Select a mood below:")
    render_mood_grid(key_suffix="moods_page")

# ==========================================================
# PAGE: MOOD RESULTS
# ==========================================================
elif st.session_state.current_page == "mood_results":
    mood = st.session_state.selected_mood

    if not mood:
        st.warning("No mood selected.")
        if st.button("← Back to Home"):
            goto_home()
        st.stop()

    mood_info = MOOD_CONFIG.get(mood, {
        "emoji": "🎬", "name": mood,
        "description": "Movie recommendations", "color": "#667eea",
    })

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("← Home", key="mood_back_home", use_container_width=True):
            goto_home()
    with col3:
        if st.button("🎭 Change Mood", key="mood_change", use_container_width=True):
            goto_moods_page()

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, {mood_info['color']}99 0%, {mood_info['color']} 100%); 
                    padding: 50px 30px; border-radius: 20px; margin: 20px 0; text-align: center;">
            <div style="font-size: 5rem; margin-bottom: 15px;">{mood_info['emoji']}</div>
            <h2 style="color: white; font-size: 2rem;">Feeling {mood_info['name']}?</h2>
            <p style="color: rgba(255,255,255,0.95); font-size: 1.2rem;">{mood_info['description']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mood_cards = []
    with st.spinner(f"🎬 Finding {mood_info['name'].lower()} movies..."):
        data, err = api_get_json("/recommend/mood", params={"mood": mood, "limit": 24})
        if not err and data:
            mood_cards = data
            random.shuffle(mood_cards)

    if mood_cards:
        st.markdown(f"### 🎬 Movies for Your {mood_info['name']} Mood ({len(mood_cards)} found)")
        poster_grid(mood_cards, cols=grid_cols, key_prefix="mood_results")
    else:
        st.warning("😕 Couldn't find movies for this mood.")
        fallback_cards, _ = api_get_json("/home", params={"category": "popular", "limit": 12})
        if fallback_cards:
            poster_grid(fallback_cards, cols=grid_cols, key_prefix="fallback_movies")

    st.divider()
    st.markdown("### 🔄 Try Another Mood")
    render_mood_grid(key_suffix="mood_results_page")

# ==========================================================
# PAGE: MOVIE DETAILS
# ==========================================================
elif st.session_state.current_page == "details":
    tmdb_id = st.session_state.selected_tmdb_id

    if not tmdb_id:
        st.warning("No movie selected.")
        if st.button("← Back to Home"):
            goto_home()
        st.stop()

    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back", use_container_width=True):
            goto_home()

    with st.spinner("Loading movie details..."):
        data, err = api_get_json(f"/movie/id/{tmdb_id}")

    if err or not data:
        st.error(f"❌ Could not load movie details: {err}")
        if st.button("🏠 Go to Home"):
            goto_home()
        st.stop()

    st.markdown("---")

    # =============================
    # MOVIE DETAILS LAYOUT
    # =============================
    left, right = st.columns([1, 2.5], gap="large")

    with left:
        # Poster
        if data.get("poster_url"):
            st.image(data["poster_url"], use_container_width=True)
        else:
            st.markdown(
                """
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            height: 450px; display: flex; align-items: center; 
                            justify-content: center; border-radius: 12px;">
                    <span style="font-size: 5rem;">🎬</span>
                </div>
                """,
                unsafe_allow_html=True
            )

        # =============================
        # WATCH TRAILER
        # =============================
        st.markdown("### 🎬 Watch Trailer")
        trailers = data.get("trailers", [])

        if trailers:
            for i, trailer in enumerate(trailers[:2]):
                youtube_url = trailer.get("youtube_url")
                trailer_name = trailer.get("name", f"Trailer {i+1}")
                if youtube_url:
                    st.link_button(
                        f"▶️ {trailer_name}",
                        youtube_url,
                        use_container_width=True
                    )
        else:
            # Fallback YouTube search
            movie_title_encoded = data.get("title", "").replace(" ", "+")
            st.link_button(
                "▶️ Search Trailer on YouTube",
                f"https://www.youtube.com/results?search_query={movie_title_encoded}+trailer",
                use_container_width=True
            )

        st.markdown("---")

        # =============================
        # WHERE TO WATCH
        # =============================
        st.markdown("### 📺 Where to Watch")
        watch_providers = data.get("watch_providers")
        movie_title_encoded = data.get("title", "").replace(" ", "+")

        if watch_providers:
            if watch_providers.get("link"):
                st.link_button(
                    "🔗 JustWatch",
                    watch_providers["link"],
                    use_container_width=True
                )

           
        else:
            st.link_button(
                "🔍 Search Online",
                f"https://www.google.com/search?q={movie_title_encoded}+watch+online",
                use_container_width=True
            )

    with right:
        # Title
        title = data.get("title", "Unknown Title")
        st.markdown(f"# {title}")

        # Tagline
        tagline = data.get("tagline")
        if tagline:
            st.markdown(f"*\"{tagline}\"*")

        # Metrics Row
        vote_avg = data.get("vote_average")
        runtime = data.get("runtime")
        vote_count = data.get("vote_count")

        col_meta = st.columns(3)
        with col_meta[0]:
            if vote_avg:
                st.metric("⭐ Rating", f"{vote_avg:.1f}/10")
        with col_meta[1]:
            if runtime:
                hours = runtime // 60
                mins = runtime % 60
                st.metric("⏱️ Runtime", f"{hours}h {mins}m" if hours else f"{mins}m")
        with col_meta[2]:
            if vote_count:
                st.metric("👥 Votes", f"{vote_count:,}")

        # Metadata
        release = data.get("release_date") or "Unknown"
        genres = ", ".join([g["name"] for g in data.get("genres", [])]) or "Unknown"

        st.markdown(f"📅 **Release Date:** {release}")
        st.markdown(f"🎭 **Genres:** {genres}")

        st.markdown("---")

        # Overview
        st.markdown("### 📖 Overview")
        overview = data.get("overview") or "No overview available."
        st.write(overview)

        st.markdown("---")

        # =============================
        # AI REVIEW SUMMARY - 
        # =============================
        st.markdown("### 🤖 AI Review Summary")

        review_summary = data.get("review_summary")

        if review_summary:
            sentiment = review_summary.get("sentiment", "Mixed")
            summary_text = review_summary.get("summary", "")
            total_reviews = review_summary.get("total_reviews", 0)
            positive_points = review_summary.get("positive_points", [])
            negative_points = review_summary.get("negative_points", [])

            sentiment_colors = {
                "Positive": ("#28a745", "#fff"),
                "Negative": ("#dc3545", "#fff"),
                "Mixed": ("#ffc107", "#000")
            }
            bg_color, text_color = sentiment_colors.get(sentiment, ("#225D97", "#030000"))

            # Sentiment Badge
            st.markdown(
                f"""
                <div style="display: inline-block; padding: 8px 16px; 
                            background-color: {bg_color}; color: {text_color}; 
                            border-radius: 20px; font-weight: bold; margin-bottom: 10px;">
                    {sentiment} Sentiment
                </div>
                """,
                unsafe_allow_html=True
            )

            # Summary Box
            st.markdown(
                f"""
                <div style="background-color: #1; padding: 20px; 
                            border-radius: 10px; border-left: 4px solid {bg_color};">
                    <p style="color: #6c757d;margin: 0; font-size: 1rem; line-height: 1.6;">
                        {summary_text}
                    </p>
                    <p style="margin-top: 10px; color: #6c757d; font-size: 0.9rem;">
                        📊 Based on {total_reviews} user reviews
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Positive and Negative Points
            if positive_points or negative_points:
                st.markdown("")
                col_pos, col_neg = st.columns(2)

                with col_pos:
                    if positive_points:
                        st.markdown("**✅ What viewers liked:**")
                        for point in positive_points:
                            st.markdown(f"• {point}")

                with col_neg:
                    if negative_points:
                        st.markdown("**❌ What viewers disliked:**")
                        for point in negative_points:
                            st.markdown(f"• {point}")

        else:
            # Show a message when no reviews exist
            st.markdown(
                """
                <div style="background-color: #f0f2f6; padding: 20px; 
                            border-radius: 10px; text-align: center;">
                    <p style="color: #6c757d;font-size: 1.1rem; margin: 0;">
                        📝 No user reviews available yet for this movie.
                    </p>
                    <p style="color: #6c757d; font-size: 0.9rem; margin-top: 8px;">
                        Be the first to share your thoughts!
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Backdrop
    if data.get("backdrop_url"):
        st.markdown("---")
        st.markdown("### 🖼️ Backdrop")
        st.image(data["backdrop_url"], use_container_width=True)

    st.divider()

    # =============================
    # RECOMMENDATIONS
    # =============================
    st.markdown("### ✨ You Might Also Like")

    title = (data.get("title") or "").strip()

    if title:
        with st.spinner("Finding similar movies..."):
            bundle, err2 = api_get_json(
                "/movie/search",
                params={"query": title, "tfidf_top_n": 12, "genre_limit": 12},
            )

            if not err2 and bundle:
                tfidf_cards = to_cards_from_tfidf_items(bundle.get("tfidf_recommendations"))
                if tfidf_cards:
                    st.markdown("#### 🔎 Similar by Content (TF-IDF)")
                    poster_grid(tfidf_cards, cols=grid_cols, key_prefix="details_tfidf")

                genre_cards = bundle.get("genre_recommendations", [])
                if genre_cards:
                    st.markdown("#### 🎭 Same Genre")
                    poster_grid(genre_cards, cols=grid_cols, key_prefix="details_genre")
            else:
                with st.spinner("Loading recommendations..."):
                    genre_only, err3 = api_get_json(
                        "/recommend/genre", params={"tmdb_id": tmdb_id, "limit": 18}
                    )
                    if not err3 and genre_only:
                        st.markdown("#### 🎭 Similar Movies")
                        poster_grid(genre_only, cols=grid_cols, key_prefix="details_genre_fallback")
                    else:
                        st.info("No recommendations available.")

    st.divider()
    st.markdown("### 🎭 Explore by Mood")
    render_mood_grid(key_suffix="details_page_mood")