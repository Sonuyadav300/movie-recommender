import os
import pickle
import random
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from collections import Counter
import re

import numpy as np
import pandas as pd
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# =========================
# ENVIRONMENT
# =========================
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p/w500"

if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY missing.")

# =========================
# APP
# =========================
app = FastAPI(title="MoodFlix API", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONSTANTS
# =========================
MOOD_TO_GENRES: Dict[str, List[int]] = {
    "Happy":       [35, 10751],
    "Sad":         [18],
    "Scared":      [27],
    "Excited":     [28, 12],
    "Romantic":    [10749],
    "Thoughtful":  [9648, 99],
    "Relaxed":     [10751, 16],
    "Adventurous": [12, 14],
    "Funny":       [35],
    "Motivated":   [99, 36],
    "Family":      [10751],
    "Mysterious":  [9648, 80],
}

MOOD_SETTINGS: Dict[str, Dict] = {
    "Happy":       {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [18, 27]},
    "Sad":         {"sort": "vote_average.desc", "min_rating": 7.5, "exclude": [35, 10751]},
    "Scared":      {"sort": "popularity.desc",   "min_rating": 6.0, "exclude": [35, 10749]},
    "Excited":     {"sort": "popularity.desc",   "min_rating": 7.0, "exclude": [18]},
    "Romantic":    {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [27, 53]},
    "Thoughtful":  {"sort": "vote_average.desc", "min_rating": 7.5, "exclude": [35]},
    "Relaxed":     {"sort": "vote_average.desc", "min_rating": 6.5, "exclude": [27, 53]},
    "Adventurous": {"sort": "popularity.desc",   "min_rating": 7.0, "exclude": [18]},
    "Funny":       {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [18, 27]},
    "Motivated":   {"sort": "vote_average.desc", "min_rating": 7.5, "exclude": [27]},
    "Family":      {"sort": "vote_average.desc", "min_rating": 6.5, "exclude": [27, 53]},
    "Mysterious":  {"sort": "vote_average.desc", "min_rating": 7.0, "exclude": [35]},
}

PLATFORMS = [
    {"name": "Netflix",     "icon": "🔴", "color": "#E50914",
     "url": "https://www.netflix.com/search?q={q}"},
    {"name": "Prime Video", "icon": "🔵", "color": "#00A8E1",
     "url": "https://www.amazon.com/s?k={q}&i=instant-video"},
    {"name": "Disney+",     "icon": "🟦", "color": "#113CCF",
     "url": "https://www.disneyplus.com/search/{q}"},
    {"name": "YouTube",     "icon": "▶️", "color": "#FF0000",
     "url": "https://www.youtube.com/results?search_query={q}+full+movie"},
    {"name": "JustWatch",   "icon": "🎬", "color": "#FF9500",
     "url": "https://www.justwatch.com/us/search?q={q}"},
]

POSITIVE_WORDS = {
    "amazing", "excellent", "outstanding", "brilliant", "fantastic",
    "wonderful", "superb", "great", "good", "love", "loved", "beautiful",
    "perfect", "incredible", "masterpiece", "stunning", "impressive",
    "enjoyable", "entertaining", "captivating", "magnificent", "terrific",
    "awesome", "phenomenal", "extraordinary", "exceptional", "remarkable",
    "best", "favorite", "recommend", "thrilling", "touching", "moving",
    "inspiring", "hilarious", "fun", "engaging", "compelling", "powerful",
    "emotional", "heartwarming", "classic", "solid", "strong", "well",
    "rich", "depth", "layered", "nuanced", "underrated", "gem",
}

NEGATIVE_WORDS = {
    "terrible", "awful", "horrible", "bad", "worst", "disappointing",
    "boring", "dull", "waste", "poor", "mediocre", "weak", "predictable",
    "overrated", "underwhelming", "forgettable", "tedious", "slow",
    "confusing", "pointless", "stupid", "ridiculous", "unrealistic",
    "annoying", "frustrating", "failed", "failure", "mess", "disaster",
    "avoid", "skip", "offensive", "flat", "bland", "uninspired",
    "cliche", "generic", "hollow", "shallow", "derivative", "formulaic",
}

DOMAIN_WORDS = {
    "acting", "storyline", "plot", "character", "characters", "direction",
    "script", "cinematography", "soundtrack", "performance", "performances",
    "effects", "visual", "visuals", "emotional", "action", "comedy",
    "drama", "thriller", "romantic", "suspense", "twist", "ending",
    "pacing", "pace", "dialogue", "cast", "director", "writing",
    "editing", "music", "score", "atmosphere", "tone", "theme",
    "chemistry", "depth", "original", "creative", "realistic",
    "authentic", "narrative", "story", "scenes",
}

# =========================
# GLOBAL STATE
# =========================
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
df:           Optional[pd.DataFrame]   = None
tfidf_matrix: Any                      = None
TITLE_TO_IDX: Optional[Dict[str, int]] = None

# =========================
# PYDANTIC MODELS
# =========================
class MovieCard(BaseModel):
    tmdb_id:      int
    title:        str
    poster_url:   Optional[str]   = None
    release_date: Optional[str]   = None
    vote_average: Optional[float] = None

class MovieDetails(BaseModel):
    tmdb_id:      int
    title:        str
    overview:     Optional[str]   = None
    release_date: Optional[str]   = None
    poster_url:   Optional[str]   = None
    backdrop_url: Optional[str]   = None
    genres:       List[dict]      = []
    vote_average: Optional[float] = None
    vote_count:   Optional[int]   = None
    runtime:      Optional[int]   = None
    tagline:      Optional[str]   = None
    status:       Optional[str]   = None
    budget:       Optional[int]   = None
    revenue:      Optional[int]   = None
    imdb_id:      Optional[str]   = None

class WatchLink(BaseModel):
    platform: str
    icon:     str
    color:    str
    url:      str

class Trailer(BaseModel):
    key:         str
    name:        str
    youtube_url: str

class ReviewItem(BaseModel):
    author:     str
    rating:     Optional[float] = None
    content:    str
    sentiment:  str
    created_at: str
    url:        str

class ReviewSummary(BaseModel):
    total_reviews:   int
    average_rating:  Optional[float] = None
    sentiment:       str
    sentiment_emoji: str
    sentiment_color: str
    positive_count:  int
    negative_count:  int
    neutral_count:   int
    key_phrases:     List[str]
    top_reviews:     List[ReviewItem]
    summary_text:    str

class WatchReviewBundle(BaseModel):
    tmdb_id:     int
    title:       str
    summary:     ReviewSummary
    watch_links: List[WatchLink]
    trailers:    List[Trailer]

class TFIDFRec(BaseModel):
    title: str
    score: float
    tmdb:  Optional[MovieCard] = None

class SearchBundle(BaseModel):
    query:                str
    movie_details:        MovieDetails
    tfidf_recommendations: List[TFIDFRec]
    genre_recommendations: List[MovieCard]

class Health(BaseModel):
    status:       str
    version:      str
    tfidf_loaded: bool
    movie_count:  int
    routes:       List[str]

# =========================
# UTILS
# =========================
def img(path: Optional[str]) -> Optional[str]:
    return f"{TMDB_IMG}{path}" if path else None

def norm(t: str) -> str:
    return str(t).strip().lower()

async def tmdb(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    q = {**params, "api_key": TMDB_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.get(f"{TMDB_BASE}{path}", params=q)
    except httpx.RequestError as e:
        raise HTTPException(502, f"TMDB network error: {e}")
    if r.status_code != 200:
        raise HTTPException(502, f"TMDB {r.status_code}: {r.text[:200]}")
    return r.json()

async def cards(results: List[dict], limit: int = 20) -> List[MovieCard]:
    return [
        MovieCard(
            tmdb_id      = int(m["id"]),
            title        = m.get("title") or m.get("name") or "",
            poster_url   = img(m.get("poster_path")),
            release_date = m.get("release_date"),
            vote_average = m.get("vote_average"),
        )
        for m in (results or [])[:limit]
    ]

async def movie_details(mid: int) -> MovieDetails:
    d = await tmdb(f"/movie/{mid}", {"language": "en-US"})
    return MovieDetails(
        tmdb_id      = int(d["id"]),
        title        = d.get("title") or "",
        overview     = d.get("overview"),
        release_date = d.get("release_date"),
        poster_url   = img(d.get("poster_path")),
        backdrop_url = img(d.get("backdrop_path")),
        genres       = d.get("genres") or [],
        vote_average = d.get("vote_average"),
        vote_count   = d.get("vote_count"),
        runtime      = d.get("runtime"),
        tagline      = d.get("tagline"),
        status       = d.get("status"),
        budget       = d.get("budget"),
        revenue      = d.get("revenue"),
        imdb_id      = d.get("imdb_id"),
    )

async def search_tmdb(query: str, page: int = 1) -> Dict[str, Any]:
    return await tmdb("/search/movie", {
        "query": query, "include_adult": "false",
        "language": "en-US", "page": page,
    })

async def search_first(query: str) -> Optional[dict]:
    d = await search_tmdb(query, 1)
    r = d.get("results", [])
    return r[0] if r else None

# =========================
# SENTIMENT
# =========================
def sentiment(text: str) -> str:
    if not text:
        return "neutral"
    tl   = text.lower()
    ws   = set(re.findall(r"\b\w+\b", tl))
    pos  = len(ws & POSITIVE_WORDS)
    neg  = len(ws & NEGATIVE_WORDS)
    negs = len(re.findall(
        r"\b(not|no|never|neither|nor|hardly|barely|"
        r"doesn't|don't|didn't|wasn't|isn't|can't|won't)\b", tl
    ))
    pos = max(0, pos - negs)
    neg = neg + negs // 2
    if pos > neg + 1: return "positive"
    if neg > pos + 1: return "negative"
    return "neutral"

def key_phrases(texts: List[str], n: int = 8) -> List[str]:
    freq: Counter = Counter()
    for t in texts:
        for w in re.findall(r"\b[a-z]{4,}\b", t.lower()):
            if w in DOMAIN_WORDS:
                freq[w] += 1
    return [w.title() for w, _ in freq.most_common(n)]

def summary_text(sent: str, pos: int, neg: int, total: int,
                 avg: Optional[float], phrases: List[str], title: str) -> str:
    if total == 0:
        return f"No reviews found for '{title}'."
    pp  = round(pos / total * 100)
    np_ = round(neg / total * 100)
    rs  = f" with an average rating of {avg:.1f}/10" if avg else ""
    ps  = f" Reviewers mention: {', '.join(phrases[:4])}." if phrases else ""
    if sent == "positive":
        return f"'{title}' has received overwhelmingly positive reviews{rs}. {pp}% of {total} reviews are positive.{ps}"
    if sent == "negative":
        return f"'{title}' has received largely negative reviews{rs}. {np_}% of {total} reviews are negative.{ps}"
    return f"'{title}' has received mixed reviews{rs}. {pp}% positive, {np_}% negative out of {total} reviews.{ps}"

# =========================
# REVIEWS & TRAILERS
# =========================
async def get_reviews(tid: int) -> List[dict]:
    out: List[dict] = []
    try:
        for page in range(1, 4):
            d     = await tmdb(f"/movie/{tid}/reviews", {"language": "en-US", "page": page})
            batch = d.get("results") or []
            out.extend(batch)
            if page >= d.get("total_pages", 1) or len(out) >= 30:
                break
        print(f"[reviews] {tid} → {len(out)} fetched")
    except Exception as e:
        print(f"[reviews] ERROR {tid}: {e}")
    return out

async def get_trailers(tid: int) -> List[Trailer]:
    try:
        d  = await tmdb(f"/movie/{tid}/videos", {"language": "en-US"})
        ts = []
        for v in d.get("results") or []:
            if v.get("site") == "YouTube" and v.get("type") in (
                "Trailer", "Teaser", "Clip", "Featurette"
            ):
                ts.append(Trailer(
                    key         = v["key"],
                    name        = v.get("name", "Video"),
                    youtube_url = f"https://www.youtube.com/watch?v={v['key']}",
                ))
        ts.sort(key=lambda x: 0 if "Official Trailer" in x.name else 1)
        print(f"[trailers] {tid} → {len(ts)} fetched")
        return ts[:5]
    except Exception as e:
        print(f"[trailers] ERROR {tid}: {e}")
        return []

def build_summary(raw: List[dict], title: str, va: Optional[float]) -> ReviewSummary:
    if not raw:
        return ReviewSummary(
            total_reviews=0, average_rating=va,
            sentiment="neutral", sentiment_emoji="😐",
            sentiment_color="#888888",
            positive_count=0, negative_count=0, neutral_count=0,
            key_phrases=[], top_reviews=[],
            summary_text=f"No written reviews yet for '{title}'."
            + (f" TMDB score: {va}/10" if va else ""),
        )

    sents, ratings, texts = [], [], []
    for r in raw:
        c = (r.get("content") or "").strip()
        if not c:
            continue
        texts.append(c)
        sents.append(sentiment(c))
        rv = (r.get("author_details") or {}).get("rating")
        if rv is not None:
            try: ratings.append(float(rv))
            except: pass

    total   = len(sents)
    pos_cnt = sents.count("positive")
    neg_cnt = sents.count("negative")
    neu_cnt = sents.count("neutral")

    if pos_cnt > neg_cnt and pos_cnt > neu_cnt:
        ov, em, co = "positive", "😊", "#22c55e"
    elif neg_cnt > pos_cnt and neg_cnt > neu_cnt:
        ov, em, co = "negative", "😞", "#ef4444"
    else:
        ov, em, co = "mixed",    "😐", "#f59e0b"

    avg_r = round(sum(ratings)/len(ratings), 1) if ratings else None
    fa    = avg_r or va
    kp    = key_phrases(texts)

    items: List[ReviewItem] = []
    for i, r in enumerate(raw[:10]):
        c = (r.get("content") or "").strip()
        if not c:
            continue
        exc = c[:500] + "…" if len(c) > 500 else c
        rv  = (r.get("author_details") or {}).get("rating")
        try:   rv_f: Optional[float] = float(rv) if rv is not None else None
        except: rv_f = None
        items.append(ReviewItem(
            author     = r.get("author") or "Anonymous",
            rating     = rv_f,
            content    = exc,
            sentiment  = sents[i] if i < len(sents) else "neutral",
            created_at = (r.get("created_at") or "")[:10],
            url        = r.get("url") or "",
        ))

    return ReviewSummary(
        total_reviews   = total,
        average_rating  = fa,
        sentiment       = ov,
        sentiment_emoji = em,
        sentiment_color = co,
        positive_count  = pos_cnt,
        negative_count  = neg_cnt,
        neutral_count   = neu_cnt,
        key_phrases     = kp,
        top_reviews     = items,
        summary_text    = summary_text(ov, pos_cnt, neg_cnt, total, fa, kp, title),
    )

def build_watch_links(title: str, imdb_id: Optional[str] = None) -> List[WatchLink]:
    q   = title.replace(" ", "+")
    qu  = title.replace(" ", "%20")
    out = []
    for p in PLATFORMS:
        url = p["url"].format(q=qu if p["name"] == "JustWatch" else q)
        out.append(WatchLink(platform=p["name"], icon=p["icon"], color=p["color"], url=url))
    if imdb_id:
        out.append(WatchLink(
            platform="IMDb", icon="⭐", color="#F5C518",
            url=f"https://www.imdb.com/title/{imdb_id}/",
        ))
    return out

# =========================
# TF-IDF
# =========================
def tfidf_recommend(query: str, n: int = 10) -> List[Tuple[str, float]]:
    if df is None or tfidf_matrix is None or TITLE_TO_IDX is None:
        return []
    key = norm(query)
    if key not in TITLE_TO_IDX:
        return []
    idx    = TITLE_TO_IDX[key]
    qv     = tfidf_matrix[idx]
    scores = (tfidf_matrix @ qv.T).toarray().ravel()
    order  = np.argsort(-scores)
    out: List[Tuple[str, float]] = []
    for i in order:
        if int(i) == idx:
            continue
        try:
            t = str(df.iloc[int(i)]["title"])
        except:
            continue
        out.append((t, float(scores[int(i)])))
        if len(out) >= n:
            break
    return out

async def card_for(title: str) -> Optional[MovieCard]:
    try:
        m = await search_first(title)
        if not m:
            return None
        return MovieCard(
            tmdb_id=int(m["id"]), title=m.get("title") or title,
            poster_url=img(m.get("poster_path")),
            release_date=m.get("release_date"),
            vote_average=m.get("vote_average"),
        )
    except:
        return None

# =========================
# STARTUP
# =========================
@app.on_event("startup")
def startup():
    global df, tfidf_matrix, TITLE_TO_IDX
    paths = {
        "df":     os.path.join(BASE_DIR, "df.pkl"),
        "idx":    os.path.join(BASE_DIR, "indices.pkl"),
        "matrix": os.path.join(BASE_DIR, "tfidf_matrix.pkl"),
        "tfidf":  os.path.join(BASE_DIR, "tfidf.pkl"),
    }
    try:
        with open(paths["df"],     "rb") as f: df           = pickle.load(f)
        with open(paths["matrix"], "rb") as f: tfidf_matrix = pickle.load(f)
        with open(paths["idx"],    "rb") as f:
            raw_idx      = pickle.load(f)
            TITLE_TO_IDX = {norm(k): int(v) for k, v in raw_idx.items()}
        print(f"✅ TF-IDF ready — {len(df)} movies")
    except FileNotFoundError as e:
        print(f"⚠️  Pickle missing: {e}")
    except Exception as e:
        print(f"⚠️  Pickle error: {e}")

# ==========================================================
#  ROUTES
#  IMPORTANT: All /api/* routes come BEFORE /movie/* routes
#  to prevent FastAPI prefix-matching conflicts
# ==========================================================

# ── Root & Health ──────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status":  "running",
        "version": "5.0",
        "routes": {
            "health":        "GET /health",
            "home":          "GET /home?category=popular&limit=24",
            "search":        "GET /tmdb/search?query=...",
            "discover":      "GET /tmdb/discover?with_genres=28",
            "movie_detail":  "GET /movie/id/{tmdb_id}",
            "movie_search":  "GET /movie/search?query=...",
            "watch_reviews": "GET /api/watch-reviews/{tmdb_id}",
            "reviews":       "GET /api/reviews/{tmdb_id}",
            "trailers":      "GET /api/trailers/{tmdb_id}",
            "watch_links":   "GET /api/watch-links/{tmdb_id}",
            "mood_recs":     "GET /recommend/mood?mood=Happy",
            "genre_recs":    "GET /recommend/genre?tmdb_id=550",
        },
    }

@app.get("/health", response_model=Health)
def health():
    return Health(
        status       = "ok",
        version      = "5.0",
        tfidf_loaded = df is not None,
        movie_count  = len(df) if df is not None else 0,
        routes       = [
            "/health", "/home", "/tmdb/search", "/tmdb/discover",
            "/movie/id/{id}", "/movie/search",
            "/api/watch-reviews/{id}", "/api/reviews/{id}",
            "/api/trailers/{id}", "/api/watch-links/{id}",
            "/recommend/mood", "/recommend/genre",
        ],
    )

# ── /api/* routes ──────────────────────────────────────────
# These MUST be registered before /movie/* to avoid conflicts

@app.get("/api/watch-reviews/{tmdb_id}", response_model=WatchReviewBundle)
async def api_watch_reviews(tmdb_id: int):
    """Combined: watch links + trailers + review summary."""
    print(f"[api/watch-reviews] tmdb_id={tmdb_id}")
    det = await movie_details(tmdb_id)
    raw_reviews, trailers = await asyncio.gather(
        get_reviews(tmdb_id),
        get_trailers(tmdb_id),
    )
    s  = build_summary(raw_reviews, det.title, det.vote_average)
    wl = build_watch_links(det.title, det.imdb_id)
    print(f"[api/watch-reviews] OK reviews={s.total_reviews} trailers={len(trailers)}")
    return WatchReviewBundle(
        tmdb_id=tmdb_id, title=det.title,
        summary=s, watch_links=wl, trailers=trailers,
    )

@app.get("/api/reviews/{tmdb_id}")
async def api_reviews(tmdb_id: int):
    """Reviews + sentiment summary."""
    det = await movie_details(tmdb_id)
    raw = await get_reviews(tmdb_id)
    s   = build_summary(raw, det.title, det.vote_average)
    return {"tmdb_id": tmdb_id, "title": det.title, "summary": s.dict()}

@app.get("/api/trailers/{tmdb_id}", response_model=List[Trailer])
async def api_trailers(tmdb_id: int):
    """YouTube trailers."""
    return await get_trailers(tmdb_id)

@app.get("/api/watch-links/{tmdb_id}", response_model=List[WatchLink])
async def api_watch_links(tmdb_id: int):
    """Streaming platform links."""
    det = await movie_details(tmdb_id)
    return build_watch_links(det.title, det.imdb_id)

# ── ping test ──────────────────────────────────────────────
@app.get("/api/ping/{tmdb_id}")
async def api_ping(tmdb_id: int):
    """Quick test — no TMDB call needed."""
    return {"ok": True, "tmdb_id": tmdb_id, "message": "api routes working"}

# ── TMDB ───────────────────────────────────────────────────
@app.get("/tmdb/search")
async def route_tmdb_search(
    query: str = Query(..., min_length=1),
    page:  int = Query(1, ge=1, le=10),
):
    return await search_tmdb(query, page)

@app.get("/tmdb/discover")
async def route_tmdb_discover(
    with_genres:    Optional[str] = Query(None),
    without_genres: Optional[str] = Query(None),
    sort_by:        str           = Query("popularity.desc"),
    page:           int           = Query(1, ge=1, le=10),
    language:       str           = Query("en-US"),
):
    p: Dict[str, Any] = {
        "language": language, "sort_by": sort_by,
        "page": page, "vote_count.gte": 50,
    }
    if with_genres:    p["with_genres"]    = with_genres
    if without_genres: p["without_genres"] = without_genres
    return await tmdb("/discover/movie", p)

# ── Home ───────────────────────────────────────────────────
@app.get("/home", response_model=List[MovieCard])
async def route_home(
    category: str = Query("popular"),
    limit:    int = Query(24, ge=1, le=50),
):
    if category == "trending":
        d = await tmdb("/trending/movie/day", {"language": "en-US"})
        return await cards(d.get("results", []), limit)
    if category not in {"popular", "top_rated", "upcoming", "now_playing"}:
        raise HTTPException(400, f"Invalid category: {category}")
    d = await tmdb(f"/movie/{category}", {"language": "en-US", "page": 1})
    return await cards(d.get("results", []), limit)

# ── Movie routes ───────────────────────────────────────────
@app.get("/movie/search", response_model=SearchBundle)
async def route_movie_search(
    query:       str = Query(..., min_length=1),
    tfidf_top_n: int = Query(12, ge=1, le=30),
    genre_limit: int = Query(12, ge=1, le=30),
):
    best = await search_first(query)
    if not best:
        raise HTTPException(404, f"No movie found: {query}")
    tid = int(best["id"])
    det = await movie_details(tid)

    recs: List[Tuple[str, float]] = []
    try:    recs = tfidf_recommend(det.title, tfidf_top_n)
    except: pass
    if not recs:
        try:    recs = tfidf_recommend(query, tfidf_top_n)
        except: pass

    tfidf_items = []
    for t, s in recs:
        c = await card_for(t)
        tfidf_items.append(TFIDFRec(title=t, score=s, tmdb=c))

    genre_recs: List[MovieCard] = []
    if det.genres:
        d = await tmdb("/discover/movie", {
            "with_genres": det.genres[0]["id"],
            "language": "en-US", "sort_by": "popularity.desc", "page": 1,
        })
        genre_recs = [c for c in await cards(d.get("results", []), genre_limit)
                      if c.tmdb_id != tid]

    return SearchBundle(
        query=query, movie_details=det,
        tfidf_recommendations=tfidf_items,
        genre_recommendations=genre_recs,
    )

@app.get("/movie/id/{tmdb_id}", response_model=MovieDetails)
async def route_movie_detail(tmdb_id: int):
    return await movie_details(tmdb_id)

# ── Recommendations ────────────────────────────────────────
@app.get("/recommend/mood", response_model=List[MovieCard])
async def route_mood(
    mood:  str = Query(...),
    limit: int = Query(24, ge=1, le=50),
    page:  int = Query(1, ge=1, le=10),
):
    mn = mood.strip().title()
    gs = MOOD_TO_GENRES.get(mn)
    if not gs:
        d = await tmdb("/movie/popular", {"language": "en-US", "page": page})
        return await cards(d.get("results", []), limit)
    s = MOOD_SETTINGS.get(mn, {"sort": "popularity.desc", "min_rating": 6.0, "exclude": []})
    p: Dict[str, Any] = {
        "with_genres": str(gs[0]), "language": "en-US",
        "sort_by": s["sort"], "page": page,
        "vote_count.gte": 50, "vote_average.gte": s["min_rating"],
    }
    if s.get("exclude"):
        p["without_genres"] = ",".join(str(g) for g in s["exclude"])
    try:
        d  = await tmdb("/discover/movie", p)
        cs = list(await cards(d.get("results", []), limit))
        random.shuffle(cs)
        return cs
    except:
        d = await tmdb("/movie/popular", {"language": "en-US", "page": 1})
        return await cards(d.get("results", []), limit)

@app.get("/recommend/genre", response_model=List[MovieCard])
async def route_genre(
    tmdb_id: int = Query(...),
    limit:   int = Query(18, ge=1, le=50),
):
    det = await movie_details(tmdb_id)
    if not det.genres:
        return []
    d  = await tmdb("/discover/movie", {
        "with_genres": det.genres[0]["id"],
        "language": "en-US", "sort_by": "popularity.desc", "page": 1,
    })
    cs = await cards(d.get("results", []), limit)
    return [c for c in cs if c.tmdb_id != tmdb_id]

@app.get("/moods")
def route_moods():
    return {"moods": [{"name": k, "genres": v} for k, v in MOOD_TO_GENRES.items()]}

# =========================
# LOCAL DEV
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)