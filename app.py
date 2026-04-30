import requests
import streamlit as st
import random

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
API_BASE = "https://movie-rec-466x.onrender.com"
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

st.set_page_config(
    page_title="MoodFlix",
    page_icon="🎬",
    layout="wide",
)

MOOD_CONFIG = {
    "Happy":       {"emoji":"😊","name":"Happy",      "description":"Feel-good comedies","color":"#FFD700","genre_ids":[35,10751],"exclude_genres":[18,27]},
    "Sad":         {"emoji":"😢","name":"Sad",        "description":"Emotional dramas",  "color":"#6495ED","genre_ids":[18],      "exclude_genres":[35,10751]},
    "Scared":      {"emoji":"😱","name":"Scared",     "description":"Horror thrillers",  "color":"#8B0000","genre_ids":[27],      "exclude_genres":[35,10749]},
    "Excited":     {"emoji":"🤩","name":"Excited",    "description":"Action adventures", "color":"#FF4500","genre_ids":[28],      "exclude_genres":[18,10749]},
    "Romantic":    {"emoji":"💕","name":"Romantic",   "description":"Love stories",      "color":"#FF69B4","genre_ids":[10749],   "exclude_genres":[27,53]},
    "Thoughtful":  {"emoji":"🤔","name":"Thoughtful", "description":"Mind-bending films","color":"#9370DB","genre_ids":[9648],    "exclude_genres":[35,10751]},
    "Relaxed":     {"emoji":"😌","name":"Relaxed",    "description":"Easy watching",     "color":"#98FB98","genre_ids":[16,10751],"exclude_genres":[27,53]},
    "Adventurous": {"emoji":"🚀","name":"Adventurous","description":"Epic journeys",     "color":"#00CED1","genre_ids":[12,14],   "exclude_genres":[18]},
    "Funny":       {"emoji":"😂","name":"Funny",      "description":"Laugh-out-loud",    "color":"#FFA500","genre_ids":[35],      "exclude_genres":[18,27]},
    "Motivated":   {"emoji":"💪","name":"Motivated",  "description":"Inspiring stories", "color":"#32CD32","genre_ids":[36,18],   "exclude_genres":[27,35]},
    "Family":      {"emoji":"👨‍👩‍👧‍👦","name":"Family","description":"For whole family",  "color":"#87CEEB","genre_ids":[10751,16],"exclude_genres":[27,53]},
    "Mysterious":  {"emoji":"🔮","name":"Mysterious", "description":"Crime mysteries",   "color":"#4B0082","genre_ids":[80,9648], "exclude_genres":[35,10751]},
}

# ─────────────────────────────────────────
# CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1400px}
.movie-title{font-size:.9rem;line-height:1.15rem;height:2.3rem;
             overflow:hidden;text-align:center;font-weight:500}
.mood-header{background:linear-gradient(135deg,#667eea,#764ba2);
             padding:30px;border-radius:20px;margin:20px 0;text-align:center}
.stImage>img{border-radius:12px;transition:transform .3s ease}
.stImage>img:hover{transform:scale(1.02)}
.stButton>button{border-radius:8px;font-weight:500;transition:all .2s ease}
.stButton>button:hover{transform:translateY(-1px)}
.stats-box{background:rgba(255,255,255,.05);border-radius:10px;
           padding:12px;text-align:center;border:1px solid rgba(255,255,255,.1)}
.phrase-tag{display:inline-block;background:rgba(102,126,234,.2);
            border:1px solid rgba(102,126,234,.4);color:#667eea;
            padding:3px 10px;border-radius:12px;font-size:.8rem;margin:3px}
#MainMenu{visibility:hidden}footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
for k, v in [
    ("current_page","home"),
    ("selected_tmdb_id",None),
    ("selected_mood",None),
    ("search_query",""),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────
# QUERY PARAMS
# ─────────────────────────────────────────
qp_page = st.query_params.get("page")
qp_id   = st.query_params.get("id")
qp_mood = st.query_params.get("mood")

if qp_page in ("home","moods","mood_results","details"):
    st.session_state.current_page = qp_page
if qp_id:
    try:
        st.session_state.selected_tmdb_id = int(qp_id)
        st.session_state.current_page     = "details"
    except: pass
if qp_mood:
    st.session_state.selected_mood = qp_mood
    st.session_state.current_page  = "mood_results"

# ─────────────────────────────────────────
# NAV
# ─────────────────────────────────────────
def goto_home():
    st.session_state.update(current_page="home",selected_mood=None,search_query="")
    st.query_params.clear(); st.query_params["page"]="home"; st.rerun()

def goto_moods():
    st.session_state.current_page="moods"
    st.query_params.clear(); st.query_params["page"]="moods"; st.rerun()

def goto_mood_results(mood:str):
    st.session_state.current_page="mood_results"
    st.session_state.selected_mood=mood
    st.query_params.clear()
    st.query_params["page"]="mood_results"
    st.query_params["mood"]=mood
    st.rerun()

def goto_details(tmdb_id:int):
    st.session_state.current_page="details"
    st.session_state.selected_tmdb_id=int(tmdb_id)
    st.query_params.clear()
    st.query_params["page"]="details"
    st.query_params["id"]=str(int(tmdb_id))
    st.rerun()

# ─────────────────────────────────────────
# API HELPERS
# ─────────────────────────────────────────
@st.cache_data(ttl=300)
def api_get(path:str, params:dict|None=None):
    """Cached — for lists, search, recommendations."""
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except requests.exceptions.Timeout:
        return None,"Timeout"
    except requests.exceptions.ConnectionError:
        return None,"Connection error"
    except Exception as e:
        return None, str(e)

def api_fresh(path:str, params:dict|None=None):
    """
    NOT cached — always fresh.
    Used for /api/watch-reviews, /api/reviews, /api/trailers, /api/watch-links
    """
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=45)
        if r.status_code >= 400:
            return None, f"HTTP {r.status_code}: {r.text[:300]}"
        return r.json(), None
    except requests.exceptions.Timeout:
        return None,"Timeout (45s)"
    except requests.exceptions.ConnectionError:
        return None,"Connection error"
    except Exception as e:
        return None, str(e)

# ─────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────
def poster_grid(movie_cards:list, cols:int=5, prefix:str="g"):
    if not movie_cards:
        st.info("No movies to show."); return
    rows = (len(movie_cards)+cols-1)//cols
    idx  = 0
    for r in range(rows):
        cs = st.columns(cols)
        for c in range(cols):
            if idx >= len(movie_cards): break
            m = movie_cards[idx]; idx+=1
            tid    = m.get("tmdb_id")
            title  = m.get("title","Untitled")
            poster = m.get("poster_url")
            year   = (m.get("release_date") or "")[:4]
            with cs[c]:
                if poster:
                    st.image(poster, use_column_width=True)
                else:
                    st.markdown(
                        '<div style="background:linear-gradient(135deg,#667eea,#764ba2);'
                        'height:280px;display:flex;align-items:center;justify-content:center;'
                        'border-radius:12px;"><span style="font-size:3rem;">🎬</span></div>',
                        unsafe_allow_html=True)
                if st.button("▶ View", key=f"{prefix}_{r}_{c}_{idx}_{tid}",
                             use_container_width=True):
                    if tid: goto_details(tid)
                st.markdown(f"<div class='movie-title'>{title}</div>",
                            unsafe_allow_html=True)
                if year:
                    st.markdown(
                        f"<div style='text-align:center;color:#888;font-size:.75rem;'>"
                        f"{year}</div>", unsafe_allow_html=True)

def mood_grid(suffix:str=""):
    ml = list(MOOD_CONFIG.values())
    for i in range(0,len(ml),4):
        cs = st.columns(4)
        for j,col in enumerate(cs):
            if i+j < len(ml):
                m = ml[i+j]
                with col:
                    if st.button(f"{m['emoji']} {m['name']}",
                                 key=f"mood_{m['name']}_{suffix}_{i}_{j}",
                                 use_container_width=True, help=m["description"]):
                        goto_mood_results(m["name"])

def tfidf_to_cards(items:list)->list:
    out=[]
    for x in items or []:
        t=x.get("tmdb") or {}
        if t.get("tmdb_id"):
            out.append({"tmdb_id":t["tmdb_id"],"title":t.get("title") or x.get("title",""),
                        "poster_url":t.get("poster_url"),"release_date":t.get("release_date")})
    return out

def parse_search(data, kw:str, limit:int=24):
    kl = kw.strip().lower()
    raw=[]
    if isinstance(data,dict) and "results" in data:
        for m in data.get("results") or []:
            title=(m.get("title") or "").strip(); tid=m.get("id"); pp=m.get("poster_path")
            if not title or not tid: continue
            raw.append({"tmdb_id":int(tid),"title":title,
                        "poster_url":f"{TMDB_IMG}{pp}" if pp else None,
                        "release_date":m.get("release_date","")})
    elif isinstance(data,list):
        for m in data:
            tid=m.get("tmdb_id") or m.get("id"); title=(m.get("title") or "").strip()
            if not title or not tid: continue
            raw.append({"tmdb_id":int(tid),"title":title,
                        "poster_url":m.get("poster_url"),"release_date":m.get("release_date","")})
    else: return [],[]
    matched=[x for x in raw if kl in x["title"].lower()]
    fl=matched if matched else raw
    sug=[]
    for x in fl[:10]:
        yr=(x.get("release_date") or "")[:4]
        sug.append((f"{x['title']} ({yr})" if yr else x["title"], x["tmdb_id"]))
    cds=[{"tmdb_id":x["tmdb_id"],"title":x["title"],
          "poster_url":x["poster_url"],"release_date":x.get("release_date")}
         for x in fl[:limit]]
    return sug,cds

# ─────────────────────────────────────────
# RENDER: WATCH LINKS
# ─────────────────────────────────────────
def render_watch_links(links:list):
    if not links: return
    st.markdown("### 🎬 Where to Watch")
    st.markdown(
        "<p style='color:#888;font-size:.9rem;margin-bottom:12px;'>"
        "Click a platform to search. Availability varies by region. "
        "<strong>JustWatch</strong> shows all local options.</p>",
        unsafe_allow_html=True)
    html="".join(
        f'<a href="{lk["url"]}" target="_blank" rel="noopener noreferrer" '
        f'style="display:inline-block;background:{lk["color"]};color:white;'
        f'padding:10px 22px;border-radius:25px;font-weight:600;font-size:.9rem;'
        f'margin:5px;text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.3);">'
        f'{lk["icon"]} {lk["platform"]}</a>'
        for lk in links)
    st.markdown(
        f'<div style="background:rgba(255,255,255,.03);'
        f'border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:20px;">'
        f'{html}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────
# RENDER: TRAILERS
# ─────────────────────────────────────────
def render_trailers(trailers:list):
    if not trailers: return
    st.markdown("### 🎞️ Trailers & Videos")
    m=trailers[0]
    st.markdown(
        f'<div style="position:relative;padding-bottom:56.25%;height:0;'
        f'overflow:hidden;border-radius:16px;margin-bottom:16px;">'
        f'<iframe src="https://www.youtube.com/embed/{m["key"]}?rel=0&modestbranding=1" '
        f'style="position:absolute;top:0;left:0;width:100%;height:100%;border:none;" '
        f'allowfullscreen allow="accelerometer;autoplay;clipboard-write;'
        f'encrypted-media;gyroscope;picture-in-picture"></iframe></div>',
        unsafe_allow_html=True)
    if len(trailers)>1:
        st.markdown("**More Videos:**")
        ec=st.columns(min(len(trailers)-1,4))
        for i,t in enumerate(trailers[1:5]):
            nm=t["name"][:30]+("…" if len(t["name"])>30 else "")
            with ec[i%len(ec)]:
                st.markdown(
                    f'<a href="{t["youtube_url"]}" target="_blank" '
                    f'style="display:block;background:rgba(255,0,0,.12);'
                    f'border:1px solid rgba(255,0,0,.3);border-radius:10px;'
                    f'padding:10px;text-align:center;text-decoration:none;'
                    f'color:#ff6b6b;font-size:.85rem;margin:4px 0;">▶ {nm}</a>',
                    unsafe_allow_html=True)

# ─────────────────────────────────────────
# RENDER: REVIEW SUMMARY
# ─────────────────────────────────────────
def render_reviews(summary:dict, movie_title:str):
    st.markdown("### 📊 Review Summary & Sentiment Analysis")
    total   = summary.get("total_reviews",0)
    sent    = summary.get("sentiment","neutral")
    s_em    = summary.get("sentiment_emoji","😐")
    s_col   = summary.get("sentiment_color","#888")
    pos_cnt = summary.get("positive_count",0)
    neg_cnt = summary.get("negative_count",0)
    neu_cnt = summary.get("neutral_count",0)
    avg_r   = summary.get("average_rating")
    phrases = summary.get("key_phrases",[])
    s_text  = summary.get("summary_text","")
    reviews = summary.get("top_reviews",[])

    # No reviews
    if total==0:
        st.markdown(
            f'<div style="background:rgba(255,255,255,.04);'
            f'border:1px solid rgba(255,255,255,.1);border-radius:14px;'
            f'padding:20px;text-align:center;">'
            f'<div style="font-size:2rem;margin-bottom:8px;">📝</div>'
            f'<p style="color:#aaa;margin:0;">{s_text or "No written reviews yet."}</p>'
            +(f'<p style="color:#FFD700;font-size:1.4rem;font-weight:700;margin-top:10px;">'
              f'⭐ {avg_r}/10</p>' if avg_r else "")
            +'</div>', unsafe_allow_html=True)
        return

    # Banner
    rd=f"⭐ {avg_r:.1f}/10" if avg_r else ""
    st.markdown(
        f'<div style="background:linear-gradient(135deg,{s_col}22,{s_col}44);'
        f'border:2px solid {s_col}66;border-radius:16px;padding:22px;margin-bottom:20px;">'
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'
        f'<div style="font-size:3.5rem;">{s_em}</div>'
        f'<div><h3 style="margin:0;color:{s_col};font-size:1.4rem;'
        f'text-transform:capitalize;">{sent} Reception</h3>'
        f'<p style="margin:4px 0 0;color:#ccc;font-size:.95rem;">'
        f'Based on {total} reviews &nbsp;{rd}</p></div></div>'
        f'<p style="margin:14px 0 0;color:#ddd;font-size:.95rem;line-height:1.6;">'
        f'{s_text}</p></div>', unsafe_allow_html=True)

    # Stats
    def stat(col,icon,val,label,color):
        col.markdown(
            f'<div class="stats-box"><div style="font-size:1.8rem;">{icon}</div>'
            f'<div style="font-size:1.4rem;font-weight:700;color:{color};">{val}</div>'
            f'<div style="font-size:.8rem;color:#888;">{label}</div></div>',
            unsafe_allow_html=True)
    c1,c2,c3,c4=st.columns(4)
    stat(c1,"😊",pos_cnt,"Positive","#22c55e")
    stat(c2,"😐",neu_cnt,"Neutral","#f59e0b")
    stat(c3,"😞",neg_cnt,"Negative","#ef4444")
    stat(c4,"⭐",f"{avg_r:.1f}" if avg_r else "N/A","Avg Rating","#FFD700")
    st.markdown("<br>",unsafe_allow_html=True)

    # Bar
    if total>0:
        pp=round(pos_cnt/total*100); np_=round(neu_cnt/total*100); ngp=100-pp-np_
        st.markdown("**Sentiment Distribution**")
        st.markdown(
            f'<div style="display:flex;height:14px;border-radius:7px;'
            f'overflow:hidden;margin:8px 0 4px;">'
            f'<div style="width:{pp}%;background:#22c55e;"></div>'
            f'<div style="width:{np_}%;background:#f59e0b;"></div>'
            f'<div style="width:{ngp}%;background:#ef4444;"></div></div>'
            f'<div style="display:flex;gap:16px;font-size:.78rem;color:#888;">'
            f'<span>🟢 Positive {pp}%</span>'
            f'<span>🟡 Neutral {np_}%</span>'
            f'<span>🔴 Negative {ngp}%</span></div>',
            unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)

    # Key phrases
    if phrases:
        st.markdown("**🏷️ What Reviewers Talk About**")
        tags=" ".join(f'<span class="phrase-tag">{p}</span>' for p in phrases)
        st.markdown(f'<div style="margin:8px 0;">{tags}</div>',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)

    # Review tabs
    if reviews:
        st.markdown("**💬 Audience Reviews**")
        t1,t2,t3=st.tabs([
            f"All ({total})",
            f"😊 Positive ({pos_cnt})",
            f"😞 Negative ({neg_cnt})",
        ])
        def one(rev:dict):
            au=rev.get("author","Anonymous"); rt=rev.get("rating")
            co=rev.get("content",""); rs=rev.get("sentiment","neutral")
            cr=rev.get("created_at",""); ur=rev.get("url","")
            sc={"positive":"#22c55e","negative":"#ef4444","neutral":"#f59e0b"}.get(rs,"#888")
            se={"positive":"😊","negative":"😞","neutral":"😐"}.get(rs,"😐")
            stars=""
            if rt:
                try: rv=float(rt); stars="⭐"*int(rv/2)+f" {rv}/10"
                except: pass
            rm=(f'<a href="{ur}" target="_blank" style="color:#667eea;font-size:.8rem;">'
                f'Read full ↗</a>' if ur else "")
            st.markdown(
                f'<div style="background:rgba(255,255,255,.04);'
                f'border:1px solid rgba(255,255,255,.1);'
                f'border-left:4px solid {sc};border-radius:12px;'
                f'padding:16px;margin:10px 0;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'align-items:center;flex-wrap:wrap;gap:8px;">'
                f'<div><span style="font-weight:600;color:#ddd;">👤 {au}</span>'
                f'<span style="margin-left:12px;color:{sc};font-size:.85rem;">'
                f'{se} {rs.title()}</span></div>'
                f'<div><span style="color:#FFD700;">{stars}</span>'
                f'<span style="color:#666;font-size:.78rem;margin-left:8px;">{cr}</span>'
                f'</div></div>'
                f'<p style="color:#bbb;font-size:.9rem;line-height:1.6;margin:10px 0 6px;">'
                f'{co}</p>{rm}</div>', unsafe_allow_html=True)
        with t1:
            for rv in reviews[:8]: one(rv)
        with t2:
            pos_r=[r for r in reviews if r.get("sentiment")=="positive"]
            [one(r) for r in pos_r] if pos_r else st.info("No positive reviews.")
        with t3:
            neg_r=[r for r in reviews if r.get("sentiment")=="negative"]
            [one(r) for r in neg_r] if neg_r else st.info("No negative reviews.")

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 Menu")
    st.markdown("---")
    if st.button("🏠 Home", use_container_width=True): goto_home()
    if st.button("🎭 Mood Picks", use_container_width=True): goto_moods()
    st.markdown("---")
    st.markdown("### 📂 Categories")
    home_cat = st.selectbox("Cat",
        ["trending","popular","top_rated","now_playing","upcoming"],
        index=0, label_visibility="collapsed")
    st.markdown("---")
    st.markdown("### ⚙️ Display")
    grid_cols = st.slider("Grid columns", 3, 8, 5)

# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:20px 0;">
<h1 style="font-size:2.8rem;margin-bottom:5px;
background:linear-gradient(135deg,#667eea,#764ba2);
-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
🎬 MoodFlix</h1>
<p style="color:#666;font-size:1.1rem;">AI Based Movie Recommendations System</p>
</div>""", unsafe_allow_html=True)
st.divider()

# ─────────────────────────────────────────
# PAGE: HOME
# ─────────────────────────────────────────
if st.session_state.current_page == "home":
    st.markdown("### 🔍 Search Movies")
    c1,c2=st.columns([5,1])
    with c1:
        typed=st.text_input("Search",value=st.session_state.search_query,
            placeholder="Type movie name: Avengers, Batman, Inception…",
            label_visibility="collapsed")
        st.session_state.search_query=typed
    with c2: st.button("🔍",use_container_width=True)

    if typed.strip():
        if len(typed.strip())<2:
            st.caption("⚠️ Type at least 2 characters.")
        else:
            with st.spinner("Searching…"):
                data,err=api_get("/tmdb/search",params={"query":typed.strip()})
            if err or data is None:
                st.error(f"❌ Search failed: {err}")
            else:
                sug,cds=parse_search(data,typed.strip(),24)
                if sug:
                    st.markdown("#### 💡 Quick Select")
                    labels=["-- Select --"]+[s[0] for s in sug]
                    sel=st.selectbox("",labels,index=0,label_visibility="collapsed")
                    if sel!="-- Select --":
                        goto_details({s[0]:s[1] for s in sug}[sel])
                if cds:
                    st.markdown(f"### 🎯 Results ({len(cds)} found)")
                    poster_grid(cds,cols=grid_cols,prefix="sr")
                else: st.info("No results.")
        st.stop()

    st.divider()
    cd=home_cat.replace("_"," ").title()
    st.markdown(f"### 🏠 {cd} Movies")
    with st.spinner(f"Loading…"):
        hc,err=api_get("/home",params={"category":home_cat,"limit":24})
    if err or not hc:
        st.error(f"❌ {err or 'Unknown error'}"); st.stop()
    poster_grid(hc,cols=grid_cols,prefix="hm")

# ─────────────────────────────────────────
# PAGE: MOODS
# ─────────────────────────────────────────
elif st.session_state.current_page == "moods":
    c1,_=st.columns([1,5])
    with c1:
        if st.button("← Home",use_container_width=True): goto_home()
    st.markdown("""
    <div class="mood-header">
    <h2 style="color:white;margin-bottom:10px;font-size:2rem;">🎭 Choose Your Mood</h2>
    <p style="color:rgba(255,255,255,.9);font-size:1.1rem;">
    Pick a mood for personalised recommendations!</p></div>""",
    unsafe_allow_html=True)
    st.markdown("#### Select a mood:")
    mood_grid("moods_page")

# ─────────────────────────────────────────
# PAGE: MOOD RESULTS
# ─────────────────────────────────────────
elif st.session_state.current_page == "mood_results":
    mood=st.session_state.selected_mood
    if not mood:
        st.warning("No mood selected.")
        if st.button("← Home"): goto_home()
        st.stop()

    mi=MOOD_CONFIG.get(mood,{"emoji":"🎬","name":mood,"description":"Movies",
       "color":"#667eea","genre_ids":[28],"exclude_genres":[]})

    c1,c2,c3=st.columns([1,3,1])
    with c1:
        if st.button("← Home",key="mb",use_container_width=True): goto_home()
    with c3:
        if st.button("🎭 Change",key="mc",use_container_width=True): goto_moods()

    st.markdown(
        f'<div style="background:linear-gradient(135deg,{mi["color"]}99,{mi["color"]});'
        f'padding:50px 30px;border-radius:20px;margin:20px 0;text-align:center;">'
        f'<div style="font-size:5rem;margin-bottom:15px;">{mi["emoji"]}</div>'
        f'<h2 style="color:white;margin-bottom:10px;font-size:2rem;">Feeling {mi["name"]}?</h2>'
        f'<p style="color:rgba(255,255,255,.95);font-size:1.2rem;">{mi["description"]}</p>'
        f'</div>', unsafe_allow_html=True)

    mc=[]
    with st.spinner(f"Finding {mi['name'].lower()} movies…"):
        pg=random.randint(1,5)
        dp={"with_genres":str(mi["genre_ids"][0]),"sort_by":"popularity.desc",
            "vote_count.gte":"50","page":str(pg),"language":"en-US"}
        if mi["exclude_genres"]:
            dp["without_genres"]=",".join(str(g) for g in mi["exclude_genres"])
        d,err=api_get("/tmdb/discover",params=dp)
        if not err and d and isinstance(d,dict) and "results" in d:
            for m in d.get("results",[])[:24]:
                pp=m.get("poster_path")
                mc.append({"tmdb_id":int(m["id"]),"title":m.get("title") or "Untitled",
                           "poster_url":f"{TMDB_IMG}{pp}" if pp else None,
                           "release_date":m.get("release_date")})
            random.shuffle(mc)
        if not mc:
            d2,_=api_get("/recommend/mood",params={"mood":mood,"limit":24})
            if d2 and isinstance(d2,list): mc=d2; random.shuffle(mc)
        if not mc:
            cat={"Happy":"popular","Sad":"top_rated","Scared":"popular","Excited":"trending",
                 "Romantic":"top_rated","Thoughtful":"top_rated","Relaxed":"popular",
                 "Adventurous":"trending","Funny":"popular","Motivated":"top_rated",
                 "Family":"popular","Mysterious":"top_rated"}.get(mood,"popular")
            d3,_=api_get("/home",params={"category":cat,"limit":24})
            if d3: mc=d3

    if mc:
        st.markdown(f"### 🎬 {mi['name']} Movies ({len(mc)} found)")
        poster_grid(mc,cols=grid_cols,prefix="mr")
    else:
        st.warning("😕 No movies found for this mood.")
        fb,_=api_get("/home",params={"category":"popular","limit":12})
        if fb: poster_grid(fb,cols=grid_cols,prefix="mfb")

    st.divider()
    st.markdown("### 🔄 Try Another Mood")
    mood_grid("mrp")

# ─────────────────────────────────────────
# PAGE: DETAILS
# ─────────────────────────────────────────
elif st.session_state.current_page == "details":
    tmdb_id=st.session_state.selected_tmdb_id
    if not tmdb_id:
        st.warning("No movie selected.")
        if st.button("← Home"): goto_home()
        st.stop()

    c1,_=st.columns([1,5])
    with c1:
        if st.button("← Back",use_container_width=True): goto_home()

    # Movie details (cached)
    with st.spinner("Loading details…"):
        data,err=api_get(f"/movie/id/{tmdb_id}")
    if err or not data:
        st.error(f"❌ {err}");
        if st.button("🏠 Home"): goto_home()
        st.stop()

    st.markdown("---")
    left,right=st.columns([1,2.5],gap="large")

    with left:
        if data.get("poster_url"):
            st.image(data["poster_url"],use_column_width=True)
        else:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#667eea,#764ba2);'
                'height:450px;display:flex;align-items:center;justify-content:center;'
                'border-radius:12px;"><span style="font-size:5rem;">🎬</span></div>',
                unsafe_allow_html=True)

    with right:
        title_str  = data.get("title","Unknown")
        tagline    = data.get("tagline") or ""
        release    = data.get("release_date") or "Unknown"
        genres_str = ", ".join(g["name"] for g in data.get("genres",[])) or "Unknown"
        runtime    = data.get("runtime")
        vote_avg   = data.get("vote_average")
        vote_count = data.get("vote_count")
        status_str = data.get("status") or ""
        budget     = data.get("budget") or 0
        revenue    = data.get("revenue") or 0

        st.markdown(f"# {title_str}")
        if tagline: st.markdown(f"*\"{tagline}\"*")

        ca,cb=st.columns(2)
        with ca:
            st.markdown(f"**📅 Release:** {release}")
            if runtime:
                h,m=divmod(runtime,60); st.markdown(f"**⏱ Runtime:** {h}h {m}m")
            st.markdown(f"**🎬 Status:** {status_str}")
        with cb:
            st.markdown(f"**🎭 Genres:** {genres_str}")
            if vote_avg:
                vc=f"({vote_count:,} votes)" if vote_count else ""
                st.markdown(f"**⭐ Rating:** {vote_avg}/10 {vc}")

        st.markdown("---")
        st.markdown("### 📖 Overview")
        st.write(data.get("overview") or "No overview available.")

        if budget or revenue:
            st.markdown("---")
            f1,f2=st.columns(2)
            with f1:
                if budget: st.markdown(f"**💰 Budget:** ${budget:,.0f}")
            with f2:
                if revenue: st.markdown(f"**💵 Revenue:** ${revenue:,.0f}")

    if data.get("backdrop_url"):
        st.markdown("### 🖼️ Backdrop")
        st.image(data["backdrop_url"],use_column_width=True)

    st.divider()

    # ═══════════════════════════════════════════════
    # STEP 1: Quick ping test to verify /api/ works
    # ═══════════════════════════════════════════════
    ping_data, ping_err = api_fresh(f"/api/ping/{tmdb_id}")

    # ═══════════════════════════════════════════════
    # STEP 2: Fetch full watch-reviews bundle
    # ═══════════════════════════════════════════════
    with st.spinner("Loading trailers, watch links & reviews…"):
        wr_data, wr_err = api_fresh(f"/api/watch-reviews/{tmdb_id}")

    # Debug expander
    with st.expander("🛠 Debug Info", expanded=False):
        st.markdown("**Ping test** (`/api/ping/{id}`) — verifies /api/ routes exist:")
        if ping_err:
            st.error(f"PING FAILED: {ping_err}")
            st.warning("⚠️ The /api/ routes are NOT accessible. Old code is running on Render. Redeploy!")
        else:
            st.success(f"✅ Ping OK: {ping_data}")

        st.markdown("**Watch-reviews** (`/api/watch-reviews/{id}`):")
        if wr_err:
            st.error(f"Error: {wr_err}")
        elif wr_data is None:
            st.warning("Returned None")
        else:
            st.success("✅ Success")
            st.json({
                "title":         wr_data.get("title"),
                "total_reviews": (wr_data.get("summary") or {}).get("total_reviews"),
                "trailers":      len(wr_data.get("trailers") or []),
                "watch_links":   len(wr_data.get("watch_links") or []),
            })

    # If ping fails, show clear message
    if ping_err:
        st.error(
            "⚠️ **API routes not updated yet.**\n\n"
            "The `/api/` routes do not exist on your deployed server. "
            "Please **push `main.py` to GitHub** and wait for Render to redeploy."
        )

    # Trailers
    trailers=(wr_data or {}).get("trailers") or []
    if not trailers:
        fb,_=api_fresh(f"/api/trailers/{tmdb_id}")
        if isinstance(fb,list): trailers=fb
    if trailers: render_trailers(trailers); st.divider()

    # Watch Links
    wl=(wr_data or {}).get("watch_links") or []
    if not wl:
        fb,_=api_fresh(f"/api/watch-links/{tmdb_id}")
        if isinstance(fb,list): wl=fb
    if wl: render_watch_links(wl); st.divider()

    # Reviews
    sd=(wr_data or {}).get("summary") or {}
    if not sd:
        fb,_=api_fresh(f"/api/reviews/{tmdb_id}")
        if isinstance(fb,dict): sd=fb.get("summary") or {}

    if sd:
        render_reviews(sd, data.get("title",""))
    else:
        st.markdown("### 📊 Audience Score")
        if vote_avg:
            vc=data.get("vote_count",0) or 0
            st.markdown(
                f'<div style="background:rgba(255,215,0,.08);'
                f'border:1px solid #FFD700;border-radius:14px;'
                f'padding:24px;text-align:center;">'
                f'<div style="font-size:3rem;">⭐</div>'
                f'<div style="font-size:2.2rem;font-weight:700;color:#FFD700;">'
                f'{vote_avg}/10</div>'
                f'<div style="color:#888;margin-top:6px;">'
                f'Based on {vc:,} TMDB votes</div></div>',
                unsafe_allow_html=True)
        else:
            st.info("No review data available.")

    st.divider()

    # Recommendations
    st.markdown("### ✨ You Might Also Like")
    tq=(data.get("title") or "").strip()
    if tq:
        with st.spinner("Finding similar movies…"):
            bundle,err2=api_get("/movie/search",
                params={"query":tq,"tfidf_top_n":12,"genre_limit":12})
        if not err2 and bundle:
            tc=tfidf_to_cards(bundle.get("tfidf_recommendations"))
            if tc:
                st.markdown("#### 🔎 Similar by Content")
                poster_grid(tc,cols=grid_cols,prefix="dt")
            gc=bundle.get("genre_recommendations",[])
            if gc:
                st.markdown("#### 🎭 Same Genre")
                poster_grid(gc,cols=grid_cols,prefix="dg")
        else:
            fb,e3=api_get("/recommend/genre",params={"tmdb_id":tmdb_id,"limit":18})
            if not e3 and fb: poster_grid(fb,cols=grid_cols,prefix="dgf")
            else: st.info("No recommendations available.")
    else:
        st.info("Cannot generate recommendations without a title.")

    st.divider()
    st.markdown("### 🎭 Explore by Mood")
    mood_grid("dp")