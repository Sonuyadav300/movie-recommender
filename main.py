import os
import pickle
import random
from typing import Optional, List, Dict, Any, Tuple

import numpy as np
import pandas as pd
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# =========================
# ENVIRONMENT VARIABLES
# =========================
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_500 = "https://image.tmdb.org/t/p/w500"

if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY missing. Add it to .env file as TMDB_API_KEY=your_key_here")

# =========================
# FASTAPI APP INITIALIZATION
# =========================
app = FastAPI(
    title="MoodFlix API",
    description="Movie recommendation API with mood-based suggestions, trailers, and AI summaries",
    version="4.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# MOOD CONFIGURATION
# =========================
MOOD_TO_GENRES = {
    "Happy": [35, 10751],
    "Sad": [18],
    "Scared": [27],
    "Excited": [28, 12],
    "Romantic": [10749],
    "Thoughtful": [9648, 99],
    "Relaxed": [10751, 16],
    "Adventurous": [12, 14],
    "Funny": [35],
    "Motivated": [99, 36],
    "Family": [10751],
    "Mysterious": [9648, 80],
}

MOOD_SETTINGS = {
    "Happy": {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [18, 27]},
    "Sad": {"sort": "vote_average.desc", "min_rating": 7.5, "exclude": [35, 10751]},
    "Scared": {"sort": "popularity.desc", "min_rating": 6.0, "exclude": [35, 10749]},
    "Excited": {"sort": "popularity.desc", "min_rating": 7.0, "exclude": [18]},
    "Romantic": {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [27, 53]},
    "Thoughtful": {"sort": "vote_average.desc", "min_rating": 7.5, "exclude": [35]},
    "Relaxed": {"sort": "vote_average.desc", "min_rating": 6.5, "exclude": [27, 53]},
    "Adventurous": {"sort": "popularity.desc", "min_rating": 7.0, "exclude": [18]},
    "Funny": {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [18, 27]},
    "Motivated": {"sort": "vote_average.desc", "min_rating": 7.5, "exclude": [27]},
    "Family": {"sort": "vote_average.desc", "min_rating": 6.5, "exclude": [27, 53]},
    "Mysterious": {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [35]},
}

# =========================
# PICKLE FILE PATHS
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DF_PATH = os.path.join(BASE_DIR, "df.pkl")
INDICES_PATH = os.path.join(BASE_DIR, "indices.pkl")
TFIDF_MATRIX_PATH = os.path.join(BASE_DIR, "tfidf_matrix.pkl")
TFIDF_PATH = os.path.join(BASE_DIR, "tfidf.pkl")

# Global variables for TF-IDF
df: Optional[pd.DataFrame] = None
indices_obj: Any = None
tfidf_matrix: Any = None
tfidf_obj: Any = None
TITLE_TO_IDX: Optional[Dict[str, int]] = None

# =========================
# PYDANTIC MODELS
# =========================
class TMDBMovieCard(BaseModel):
    tmdb_id: int
    title: str
    poster_url: Optional[str] = None
    release_date: Optional[str] = None
    vote_average: Optional[float] = None

class TrailerInfo(BaseModel):
    key: str
    name: str
    site: str
    type: str
    youtube_url: str

class WatchProvider(BaseModel):
    provider_id: int
    provider_name: str
    logo_path: Optional[str] = None

class WatchProviders(BaseModel):
    link: Optional[str] = None
    flatrate: List[WatchProvider] = []
    rent: List[WatchProvider] = []
    buy: List[WatchProvider] = []

class ReviewSummary(BaseModel):
    summary: str
    sentiment: str
    total_reviews: int
    positive_points: List[str] = []
    negative_points: List[str] = []

class TMDBMovieDetails(BaseModel):
    tmdb_id: int
    title: str
    overview: Optional[str] = None
    release_date: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    genres: List[dict] = []
    trailers: List[TrailerInfo] = []
    watch_providers: Optional[WatchProviders] = None
    review_summary: Optional[ReviewSummary] = None
    runtime: Optional[int] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    tagline: Optional[str] = None

class TFIDFRecItem(BaseModel):
    title: str
    score: float
    tmdb: Optional[TMDBMovieCard] = None

class SearchBundleResponse(BaseModel):
    query: str
    movie_details: TMDBMovieDetails
    tfidf_recommendations: List[TFIDFRecItem]
    genre_recommendations: List[TMDBMovieCard]

class MoodInfo(BaseModel):
    name: str
    emoji: str
    description: str

class HealthResponse(BaseModel):
    status: str
    tfidf_loaded: bool
    movie_count: int

# =========================
# UTILITY FUNCTIONS
# =========================
def _norm_title(t: str) -> str:
    """Normalize title for comparison"""
    return str(t).strip().lower()

def make_img_url(path: Optional[str]) -> Optional[str]:
    """Create full TMDB image URL"""
    if not path:
        return None
    return f"{TMDB_IMG_500}{path}"

async def tmdb_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make GET request to TMDB API"""
    q = dict(params)
    q["api_key"] = TMDB_API_KEY
    
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{TMDB_BASE}{path}", params=q)
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"TMDB request error: {type(e).__name__}"
        )
    
    if r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"TMDB error {r.status_code}: {r.text[:200]}"
        )
    
    return r.json()

async def tmdb_cards_from_results(
    results: List[dict],
    limit: int = 20
) -> List[TMDBMovieCard]:
    """Convert TMDB results to movie cards"""
    out: List[TMDBMovieCard] = []
    for m in (results or [])[:limit]:
        out.append(
            TMDBMovieCard(
                tmdb_id=int(m["id"]),
                title=m.get("title") or m.get("name") or "",
                poster_url=make_img_url(m.get("poster_path")),
                release_date=m.get("release_date"),
                vote_average=m.get("vote_average"),
            )
        )
    return out

async def tmdb_search_movies(query: str, page: int = 1) -> Dict[str, Any]:
    """Search movies on TMDB"""
    return await tmdb_get(
        "/search/movie",
        {
            "query": query,
            "include_adult": "false",
            "language": "en-US",
            "page": page,
        },
    )

async def tmdb_search_first(query: str) -> Optional[dict]:
    """Get first movie from TMDB search"""
    data = await tmdb_search_movies(query=query, page=1)
    results = data.get("results", [])
    return results[0] if results else None

# =========================
# NEW FUNCTIONS FOR TRAILERS & REVIEWS
# =========================

async def get_movie_trailers(movie_id: int) -> List[TrailerInfo]:
    """Get movie trailers from TMDB"""
    try:
        data = await tmdb_get(f"/movie/{movie_id}/videos", {"language": "en-US"})
        trailers = []
        
        for video in data.get("results", []):
            if video.get("site") == "YouTube" and video.get("type") in ["Trailer", "Teaser"]:
                trailers.append(TrailerInfo(
                    key=video["key"],
                    name=video.get("name", "Trailer"),
                    site=video["site"],
                    type=video["type"],
                    youtube_url=f"https://www.youtube.com/watch?v={video['key']}"
                ))
        
        return trailers
    except Exception as e:
        print(f"Error fetching trailers: {e}")
        return []

async def get_watch_providers(movie_id: int) -> Optional[WatchProviders]:
    """Get streaming availability from TMDB"""
    try:
        data = await tmdb_get(f"/movie/{movie_id}/watch/providers", {})
        results = data.get("results", {})
        
        # Focus on US providers (change country code as needed)
        us_providers = results.get("US", {})
        
        if not us_providers:
            return None
        
        def parse_providers(provider_list):
            return [
                WatchProvider(
                    provider_id=p["provider_id"],
                    provider_name=p["provider_name"],
                    logo_path=make_img_url(p.get("logo_path"))
                )
                for p in (provider_list or [])
            ]
        
        return WatchProviders(
            link=us_providers.get("link"),
            flatrate=parse_providers(us_providers.get("flatrate", [])),
            rent=parse_providers(us_providers.get("rent", [])),
            buy=parse_providers(us_providers.get("buy", []))
        )
    except Exception as e:
        print(f"Error fetching watch providers: {e}")
        return None

async def get_movie_reviews(movie_id: int, max_reviews: int = 10) -> List[dict]:
    """Get movie reviews from TMDB"""
    try:
        data = await tmdb_get(f"/movie/{movie_id}/reviews", {"language": "en-US", "page": 1})
        return data.get("results", [])[:max_reviews]
    except Exception as e:
        print(f"Error fetching reviews: {e}")
        return []

async def generate_ai_summary(reviews: List[dict], movie_title: str) -> Optional[ReviewSummary]:
    """Generate AI-based summary of reviews"""
    if not reviews:
        return None
    
    try:
        # Extract review contents
        review_texts = [r.get("content", "")[:1000] for r in reviews if r.get("content")]
        
        if not review_texts:
            return None
        
        total_reviews = len(review_texts)
        
        # Try OpenAI first if API key is available
        if OPENAI_API_KEY:
            try:
                summary_data = await generate_openai_summary(review_texts, movie_title)
                if summary_data:
                    return summary_data
            except Exception as e:
                print(f"OpenAI error, falling back to basic analysis: {e}")
        
        # Fallback to basic sentiment analysis
        positive_keywords = ["good", "great", "excellent", "amazing", "love", "best", 
                           "wonderful", "fantastic", "perfect", "brilliant", "masterpiece"]
        negative_keywords = ["bad", "worst", "terrible", "awful", "hate", "boring", 
                           "disappointing", "poor", "waste", "dull"]
        
        positive_count = 0
        negative_count = 0
        positive_points = []
        negative_points = []
        
        for text in review_texts:
            text_lower = text.lower()
            pos = sum(1 for word in positive_keywords if word in text_lower)
            neg = sum(1 for word in negative_keywords if word in text_lower)
            positive_count += pos
            negative_count += neg
            
            # Extract sample points
            if pos > neg and len(positive_points) < 3:
                sentences = text.split('.')
                for sentence in sentences[:2]:
                    if any(word in sentence.lower() for word in positive_keywords):
                        positive_points.append(sentence.strip()[:100])
                        break
            elif neg > pos and len(negative_points) < 3:
                sentences = text.split('.')
                for sentence in sentences[:2]:
                    if any(word in sentence.lower() for word in negative_keywords):
                        negative_points.append(sentence.strip()[:100])
                        break
        
        # Determine sentiment
        if positive_count > negative_count * 1.5:
            sentiment = "Positive"
            summary = f"{movie_title} receives mostly positive reviews. Viewers praise its storytelling, performances, and overall entertainment value. Critics highlight its engaging plot and memorable moments."
        elif negative_count > positive_count * 1.5:
            sentiment = "Negative"
            summary = f"{movie_title} has received mixed to negative reviews. Some viewers found issues with pacing, plot development, or execution. Critics noted areas where the film could have been improved."
        else:
            sentiment = "Mixed"
            summary = f"{movie_title} receives mixed reviews from audiences. Opinions vary on its quality, with both praise and criticism. While some enjoy the concept, others feel it falls short in certain aspects."
        
        return ReviewSummary(
            summary=summary,
            sentiment=sentiment,
            total_reviews=total_reviews,
            positive_points=positive_points[:3],
            negative_points=negative_points[:3]
        )
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return None

async def generate_openai_summary(review_texts: List[str], movie_title: str) -> Optional[ReviewSummary]:
    """Generate summary using OpenAI GPT"""
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        combined_reviews = "\n\n".join(review_texts[:5])
        
        prompt = f"""Analyze the following movie reviews for '{movie_title}' and provide:
1. A 2-3 sentence summary
2. Overall sentiment (Positive/Negative/Mixed)
3. 2-3 positive points (as bullet points)
4. 2-3 negative points (as bullet points)

Reviews:
{combined_reviews}

Respond in this exact JSON format:
{{
    "summary": "your summary here",
    "sentiment": "Positive/Negative/Mixed",
    "positive_points": ["point 1", "point 2"],
    "negative_points": ["point 1", "point 2"]
}}"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a movie review analyzer. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        return ReviewSummary(
            summary=result.get("summary", ""),
            sentiment=result.get("sentiment", "Mixed"),
            total_reviews=len(review_texts),
            positive_points=result.get("positive_points", [])[:3],
            negative_points=result.get("negative_points", [])[:3]
        )
        
    except Exception as e:
        print(f"OpenAI error: {e}")
        return None

# =========================
# TF-IDF HELPER FUNCTIONS
# =========================
def build_title_to_idx_map(indices: Any) -> Dict[str, int]:
    """Build title to index mapping"""
    title_to_idx: Dict[str, int] = {}
    
    if isinstance(indices, dict):
        for k, v in indices.items():
            title_to_idx[_norm_title(k)] = int(v)
        return title_to_idx
    
    try:
        for k, v in indices.items():
            title_to_idx[_norm_title(k)] = int(v)
        return title_to_idx
    except Exception:
        raise RuntimeError("indices.pkl must be dict or pandas Series-like")

def get_local_idx_by_title(title: str) -> int:
    """Get local index for a movie title"""
    global TITLE_TO_IDX
    if TITLE_TO_IDX is None:
        raise HTTPException(status_code=500, detail="TF-IDF not initialized")
    key = _norm_title(title)
    if key in TITLE_TO_IDX:
        return int(TITLE_TO_IDX[key])
    raise HTTPException(status_code=404, detail=f"Title not found: '{title}'")

def tfidf_recommend_titles(query_title: str, top_n: int = 10) -> List[Tuple[str, float]]:
    """Get TF-IDF based recommendations"""
    global df, tfidf_matrix
    if df is None or tfidf_matrix is None:
        raise HTTPException(status_code=500, detail="TF-IDF not loaded")
    
    idx = get_local_idx_by_title(query_title)
    qv = tfidf_matrix[idx]
    scores = (tfidf_matrix @ qv.T).toarray().ravel()
    order = np.argsort(-scores)
    
    out: List[Tuple[str, float]] = []
    for i in order:
        if int(i) == int(idx):
            continue
        try:
            title_i = str(df.iloc[int(i)]["title"])
        except Exception:
            continue
        out.append((title_i, float(scores[int(i)])))
        if len(out) >= top_n:
            break
    return out

async def attach_tmdb_card_by_title(title: str) -> Optional[TMDBMovieCard]:
    """Attach TMDB card to a title"""
    try:
        m = await tmdb_search_first(title)
        if not m:
            return None
        return TMDBMovieCard(
            tmdb_id=int(m["id"]),
            title=m.get("title") or title,
            poster_url=make_img_url(m.get("poster_path")),
            release_date=m.get("release_date"),
            vote_average=m.get("vote_average"),
        )
    except Exception:
        return None

# =========================
# STARTUP EVENT
# =========================
@app.on_event("startup")
def load_pickles():
    """Load pickle files on startup"""
    global df, indices_obj, tfidf_matrix, tfidf_obj, TITLE_TO_IDX
    
    try:
        with open(DF_PATH, "rb") as f:
            df = pickle.load(f)
        with open(INDICES_PATH, "rb") as f:
            indices_obj = pickle.load(f)
        with open(TFIDF_MATRIX_PATH, "rb") as f:
            tfidf_matrix = pickle.load(f)
        with open(TFIDF_PATH, "rb") as f:
            tfidf_obj = pickle.load(f)
        
        TITLE_TO_IDX = build_title_to_idx_map(indices_obj)
        print(f"✅ Loaded {len(df)} movies from pickle files")
    except FileNotFoundError as e:
        print(f"⚠️ Pickle file not found: {e}. TF-IDF features disabled.")
    except Exception as e:
        print(f"⚠️ Error loading pickles: {e}. TF-IDF features disabled.")

# =========================
# API ROUTES
# =========================
@app.get("/")
def root():
    """Root endpoint - API info"""
    return {
        "message": "🎬 MoodFlix API is running!",
        "version": "4.0",
        "features": [
            "Movie search and discovery",
            "Mood-based recommendations",
            "Trailer links",
            "Watch provider information",
            "AI-powered review summaries",
            "TF-IDF content-based recommendations"
        ],
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "home": "/home",
            "search": "/tmdb/search",
            "discover": "/tmdb/discover",
            "movie_details": "/movie/id/{tmdb_id}",
            "mood_recommendations": "/recommend/mood",
            "genre_recommendations": "/recommend/genre",
            "moods_list": "/moods",
        }
    }

@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint"""
    return HealthResponse(
        status="ok",
        tfidf_loaded=df is not None,
        movie_count=len(df) if df is not None else 0
    )

@app.get("/moods")
def get_available_moods():
    """Get list of available moods"""
    return {
        "moods": [
            {"name": "Happy", "emoji": "😊", "description": "Feel-good comedies and uplifting stories"},
            {"name": "Sad", "emoji": "😢", "description": "Emotional dramas and tearjerkers"},
            {"name": "Scared", "emoji": "😱", "description": "Horror and spine-chilling thrillers"},
            {"name": "Excited", "emoji": "🤩", "description": "Action-packed adventures"},
            {"name": "Romantic", "emoji": "💕", "description": "Love stories and romantic comedies"},
            {"name": "Thoughtful", "emoji": "🤔", "description": "Mind-bending mysteries and thrillers"},
            {"name": "Relaxed", "emoji": "😌", "description": "Light-hearted and easy watching"},
            {"name": "Adventurous", "emoji": "🚀", "description": "Epic journeys and fantasy worlds"},
            {"name": "Funny", "emoji": "😂", "description": "Laugh-out-loud comedies"},
            {"name": "Motivated", "emoji": "💪", "description": "Inspiring true stories and sports dramas"},
            {"name": "Family", "emoji": "👨‍👩‍👧‍👦", "description": "Fun for the whole family"},
            {"name": "Mysterious", "emoji": "🔮", "description": "Crime and detective stories"},
        ]
    }

@app.get("/home", response_model=List[TMDBMovieCard])
async def home(
    category: str = Query("popular", description="Category: trending, popular, top_rated, now_playing, upcoming"),
    limit: int = Query(24, ge=1, le=50),
):
    """Get home feed movies by category"""
    try:
        if category == "trending":
            data = await tmdb_get("/trending/movie/day", {"language": "en-US"})
            return await tmdb_cards_from_results(data.get("results", []), limit=limit)
        
        if category not in {"popular", "top_rated", "upcoming", "now_playing"}:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        
        data = await tmdb_get(f"/movie/{category}", {"language": "en-US", "page": 1})
        return await tmdb_cards_from_results(data.get("results", []), limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch movies: {e}")

@app.get("/tmdb/search")
async def tmdb_search(
    query: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, le=10),
):
    """Search movies on TMDB"""
    return await tmdb_search_movies(query=query, page=page)

@app.get("/tmdb/discover")
async def tmdb_discover(
    with_genres: Optional[str] = Query(None, description="Genre IDs (comma-separated)"),
    without_genres: Optional[str] = Query(None, description="Exclude genre IDs"),
    sort_by: str = Query("popularity.desc"),
    page: int = Query(1, ge=1, le=10),
    language: str = Query("en-US"),
):
    """TMDB Discover endpoint - for mood-based recommendations"""
    params = {
        "language": language,
        "sort_by": sort_by,
        "page": page,
        "vote_count.gte": 50,
    }
    
    if with_genres:
        params["with_genres"] = with_genres
    if without_genres:
        params["without_genres"] = without_genres
    
    return await tmdb_get("/discover/movie", params)

@app.get("/movie/id/{tmdb_id}", response_model=TMDBMovieDetails)
async def movie_details_route(tmdb_id: int):
    """Get comprehensive movie details including trailers, watch providers, and AI review summary"""
    
    # Get basic details
    data = await tmdb_get(f"/movie/{tmdb_id}", {"language": "en-US"})
    
    # Get trailers
    trailers = await get_movie_trailers(tmdb_id)
    
    # Get watch providers
    watch_providers = await get_watch_providers(tmdb_id)
    
    # Get reviews and generate AI summary
    reviews = await get_movie_reviews(tmdb_id, max_reviews=10)
    review_summary = await generate_ai_summary(reviews, data.get("title", ""))
    
    return TMDBMovieDetails(
        tmdb_id=int(data["id"]),
        title=data.get("title") or "",
        overview=data.get("overview"),
        release_date=data.get("release_date"),
        poster_url=make_img_url(data.get("poster_path")),
        backdrop_url=make_img_url(data.get("backdrop_path")),
        genres=data.get("genres", []) or [],
        trailers=trailers,
        watch_providers=watch_providers,
        review_summary=review_summary,
        runtime=data.get("runtime"),
        vote_average=data.get("vote_average"),
        vote_count=data.get("vote_count"),
        tagline=data.get("tagline")
    )

@app.get("/recommend/mood", response_model=List[TMDBMovieCard])
async def recommend_by_mood(
    mood: str = Query(..., description="User's current mood"),
    limit: int = Query(24, ge=1, le=50),
    page: int = Query(1, ge=1, le=10),
):
    """Get movie recommendations based on mood"""
    mood_normalized = mood.strip().title()
    genre_ids = MOOD_TO_GENRES.get(mood_normalized)
    
    if not genre_ids:
        # Fallback to popular
        data = await tmdb_get("/movie/popular", {"language": "en-US", "page": page})
        return await tmdb_cards_from_results(data.get("results", []), limit=limit)
    
    settings = MOOD_SETTINGS.get(mood_normalized, {
        "sort": "popularity.desc",
        "min_rating": 6.0,
        "exclude": []
    })
    
    # Use primary genre
    primary_genre = genre_ids[0]
    exclude_genres = settings.get("exclude", [])
    
    discover_params = {
        "with_genres": str(primary_genre),
        "language": "en-US",
        "sort_by": settings["sort"],
        "page": page,
        "vote_count.gte": 50,
        "vote_average.gte": settings["min_rating"],
    }
    
    if exclude_genres:
        discover_params["without_genres"] = ",".join(str(g) for g in exclude_genres)
    
    try:
        data = await tmdb_get("/discover/movie", discover_params)
        cards = await tmdb_cards_from_results(data.get("results", []), limit=limit)
        
        # Shuffle for variety
        cards_list = list(cards)
        random.shuffle(cards_list)
        
        # If not enough, try with relaxed filters
        if len(cards_list) < limit // 2:
            discover_params["vote_count.gte"] = 20
            discover_params["vote_average.gte"] = 5.5
            data = await tmdb_get("/discover/movie", discover_params)
            cards = await tmdb_cards_from_results(data.get("results", []), limit=limit)
            cards_list = list(cards)
            random.shuffle(cards_list)
        
        return cards_list[:limit]
    except Exception as e:
        print(f"Mood recommendation error: {e}")
        data = await tmdb_get("/movie/popular", {"language": "en-US", "page": 1})
        return await tmdb_cards_from_results(data.get("results", []), limit=limit)

@app.get("/recommend/genre", response_model=List[TMDBMovieCard])
async def recommend_genre(
    tmdb_id: int = Query(..., description="TMDB movie ID"),
    limit: int = Query(18, ge=1, le=50),
):
    """Get recommendations based on movie's genre"""
    details = await tmdb_get(f"/movie/{tmdb_id}", {"language": "en-US"})
    genres = details.get("genres", [])
    
    if not genres:
        return []
    
    genre_id = genres[0]["id"]
    discover = await tmdb_get(
        "/discover/movie",
        {
            "with_genres": genre_id,
            "language": "en-US",
            "sort_by": "popularity.desc",
            "page": 1,
        },
    )
    cards = await tmdb_cards_from_results(discover.get("results", []), limit=limit)
    return [c for c in cards if c.tmdb_id != tmdb_id]

@app.get("/recommend/tfidf")
async def recommend_tfidf(
    title: str = Query(..., min_length=1, description="Movie title"),
    top_n: int = Query(10, ge=1, le=50),
):
    """Get TF-IDF based recommendations"""
    if df is None:
        raise HTTPException(status_code=503, detail="TF-IDF model not loaded")
    
    recs = tfidf_recommend_titles(title, top_n=top_n)
    return [{"title": t, "score": s} for t, s in recs]

@app.get("/movie/search", response_model=SearchBundleResponse)
async def search_bundle(
    query: str = Query(..., min_length=1, description="Search query"),
    tfidf_top_n: int = Query(12, ge=1, le=30),
    genre_limit: int = Query(12, ge=1, le=30),
):
    """Search movie and get bundled recommendations"""
    best = await tmdb_search_first(query)
    if not best:
        raise HTTPException(status_code=404, detail=f"No movie found for: {query}")
    
    tmdb_id = int(best["id"])
    
    # Get full details with trailers and reviews
    details = await movie_details_route(tmdb_id)
    
    # TF-IDF recommendations
    tfidf_items: List[TFIDFRecItem] = []
    
    if df is not None:
        try:
            recs = tfidf_recommend_titles(details.title, top_n=tfidf_top_n)
        except Exception:
            try:
                recs = tfidf_recommend_titles(query, top_n=tfidf_top_n)
            except Exception:
                recs = []
        
        for title, score in recs:
            card = await attach_tmdb_card_by_title(title)
            tfidf_items.append(TFIDFRecItem(title=title, score=score, tmdb=card))
    
    # Genre recommendations
    genre_recs: List[TMDBMovieCard] = []
    if details.genres:
        genre_id = details.genres[0]["id"]
        discover = await tmdb_get(
            "/discover/movie",
            {
                "with_genres": genre_id,
                "language": "en-US",
                "sort_by": "popularity.desc",
                "page": 1,
            },
        )
        cards = await tmdb_cards_from_results(
            discover.get("results", []), limit=genre_limit
        )
        genre_recs = [c for c in cards if c.tmdb_id != details.tmdb_id]
    
    return SearchBundleResponse(
        query=query,
        movie_details=details,
        tfidf_recommendations=tfidf_items,
        genre_recommendations=genre_recs,
    )

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)