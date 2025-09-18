# src/youtube/scraper.py
# Safe plan: 1 page (top-50) per 4-month window, ~6,262 units total.

import csv, json, time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import requests

SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"

# Root-aware defaults
ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "assets"; ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_CSV_PATH    = ASSETS_DIR / "yt_counter_strike.csv"
DEFAULT_STATE_PATH  = ASSETS_DIR / "yt_counter_strike_state.json"
DEFAULT_TOKENS_PATH = ROOT / "data" / "tokens.json"

# ---- Hardcoded Google OAuth client credentials ----
CLIENT_ID     = "823344079673-gnpgl76j79rvbp0h8ne81jrke1ngs4j6.apps.googleusercontent.com"
CLIENT_SECRET = "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"

# Quota costs
COST_SEARCH = 100
COST_VIDEOS = 1
COST_PER_PAGE = COST_SEARCH + COST_VIDEOS  # 101

BASE_SLEEP = 0.25

FIELDS = [
    "videoId","publishedAt","channelId","channelTitle","title","description",
    "viewCount","likeCount","commentCount","favoriteCount","categoryId"
]

# -------------------- Token manager --------------------
def _load_tokens(path: Path) -> Dict:
    if not path.exists():
        raise RuntimeError(f"{path} not found. Run scripts/google_oauth.py first.")
    return json.loads(path.read_text())

def _save_tokens(path: Path, tokens: Dict) -> None:
    path.write_text(json.dumps(tokens, indent=2))

def _refresh(tokens: Dict, cid: str, cs: str) -> Dict:
    if "refresh_token" not in tokens:
        raise RuntimeError("No refresh_token present. Re-run google_oauth.py with prompt=consent.")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": cid,
        "client_secret": cs,
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=30)
    r.raise_for_status()
    new_tokens = r.json()
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    return new_tokens

class _TokenManager:
    def __init__(self, path: Path, cid: str, cs: str):
        self.path = path; self.cid = cid; self.cs = cs
        self.tokens = _load_tokens(path)
        self.expiry = time.time() + float(self.tokens.get("expires_in", 0)) - 30

    def header(self) -> Dict[str, str]:
        if time.time() >= self.expiry and self.tokens.get("refresh_token"):
            self._do_refresh()
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def _do_refresh(self):
        new_tokens = _refresh(self.tokens, self.cid, self.cs)
        self.tokens.update(new_tokens)
        _save_tokens(self.path, self.tokens)
        self.expiry = time.time() + float(self.tokens.get("expires_in", 0)) - 30

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {}) or {}
        headers |= self.header()
        r = requests.request(method, url, headers=headers, **kwargs)
        if r.status_code == 401 and self.tokens.get("refresh_token"):
            self._do_refresh()
            headers = kwargs.pop("headers", {}) or {}
            headers |= self.header()
            r = requests.request(method, url, headers=headers, **kwargs)
        return r

# -------------------- 4-month windows --------------------
def _add_months(y: int, m: int, d: int) -> tuple[int,int]:
    idx = (y-1)*12 + (m-1) + d
    return idx//12+1, idx%12+1

def _windows(start: str, end: str) -> List[Tuple[str,str]]:
    def ym(s: str) -> tuple[int,int]:
        return int(s[:4]), int(s[5:7])
    sy, sm = ym(start); ey, em = ym(end)
    ey2, em2 = _add_months(ey, em, 1)  # exclusive bound

    out = []
    y, m = sy, sm
    while (y, m) < (ey2, em2):
        y2, m2 = _add_months(y, m, 4)
        pa = f"{y:04d}-{m:02d}-01T00:00:00Z"
        pb = f"{y2:04d}-{m2:02d}-01T00:00:00Z"
        if (y2, m2) > (ey2, em2):
            pb = f"{ey2:04d}-{em2:02d}-01T00:00:00Z"
        out.append((pa, pb))
        y, m = y2, m2
    return out

# -------------------- One page fetch --------------------
def _fetch_one_page(tm: _TokenManager, query: str, order: str, batch_size: int,
                    csv_path: Path, published_after: str, published_before: str) -> int:
    # search
    r = tm.request("GET", SEARCH_URL, params={
        "part":"id","q":query,"type":"video","maxResults":batch_size,
        "order":order,"publishedAfter":published_after,"publishedBefore":published_before
    }, timeout=30)
    r.raise_for_status()
    ids = [it["id"]["videoId"] for it in r.json().get("items", []) if "videoId" in it.get("id",{})]
    if not ids: return 0

    # videos
    r2 = tm.request("GET", VIDEOS_URL, params={
        "part":"snippet,statistics","id":",".join(ids),"maxResults":batch_size
    }, timeout=30)
    r2.raise_for_status()

    if not csv_path.exists():
        with open(csv_path,"w",newline="",encoding="utf-8") as f:
            csv.DictWriter(f,fieldnames=FIELDS).writeheader()

    items = r2.json().get("items",[])
    with open(csv_path,"a",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f,fieldnames=FIELDS)
        for it in items:
            s,st = it.get("snippet",{}), it.get("statistics",{})
            w.writerow({
                "videoId": it.get("id"),
                "publishedAt": s.get("publishedAt"),
                "channelId": s.get("channelId"),
                "channelTitle": s.get("channelTitle"),
                "title": s.get("title"),
                "description": s.get("description"),
                "viewCount": st.get("viewCount"),
                "likeCount": st.get("likeCount"),
                "commentCount": st.get("commentCount"),
                "favoriteCount": st.get("favoriteCount"),
                "categoryId": s.get("categoryId"),
            })
    return len(items)

# -------------------- Public API --------------------
def scrape_4mo_top50(
    start: str = "2005-04",
    end: Optional[str] = None,
    query: str = "counter strike",
    order: str = "viewCount",
    batch_size: int = 50,
    csv_path: Optional[str|Path] = None,
    state_path: Optional[str|Path] = None,
    tokens_path: Optional[str|Path] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> int:
    csv_path    = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
    state_path  = Path(state_path) if state_path else DEFAULT_STATE_PATH
    tokens_path = Path(tokens_path) if tokens_path else DEFAULT_TOKENS_PATH
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if end is None:
        end = datetime.utcnow().strftime("%Y-%m")

    tm = _TokenManager(tokens_path, client_id or CLIENT_ID, client_secret or CLIENT_SECRET)
    windows = _windows(start, end)

    # resume
    resume_idx = 0
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text())
            win = st.get("window")
            if win:
                cur = (win["publishedAfter"], win["publishedBefore"])
                for i,w in enumerate(windows):
                    if w == cur: resume_idx=i+1; break
        except: pass

    total=0
    for i in range(resume_idx,len(windows)):
        pa,pb=windows[i]
        rows=_fetch_one_page(tm,query,order,batch_size,csv_path,pa,pb)
        total+=rows
        state_path.write_text(json.dumps({
            "mode":"4mo_top50","window":{"publishedAfter":pa,"publishedBefore":pb}
        },indent=2))
        print(f"[{pa} → {pb}) {rows} rows; total {total}")
        time.sleep(0.05)

    print(f"\nDone. Total rows {total} | CSV: {csv_path}")
    return total

def scrape(*args, **kwargs) -> int:
    return scrape_4mo_top50(*args, **kwargs)

if __name__=="__main__":
    scrape_4mo_top50(
        start="2005-04",
        end=datetime.utcnow().strftime("%Y-%m"),
        query="counter strike",
        order="viewCount",
        batch_size=50,
        csv_path=DEFAULT_CSV_PATH,
        state_path=DEFAULT_STATE_PATH,
        tokens_path=DEFAULT_TOKENS_PATH,
    )
