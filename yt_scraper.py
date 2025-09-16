# yt_scraper.py
# Loads tokens.json created by oauth_flow.py and
# pulls paginated results from search.list, enriches with videos.list,
# auto-refreshes tokens using hardcoded CLIENT_ID/SECRET,
# and streams rows to CSV with resume support.

import csv, json, time
from pathlib import Path
from typing import Dict
import requests

TOKENS_PATH = "tokens.json"        # produced by oauth_flow.py
SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"

# ---- Hardcoded Google OAuth client credentials ----
CLIENT_ID     = "YOUR_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"

# ---- Tweak these for your run ----
QUERY       = "counterstrike"     # search query
ORDER       = "viewCount"          # most viewed first
TARGET      = 200_000              # stops earlier if pagination ends (~25k cap per single query)
BATCH_SIZE  = 50                   # max per API request
CSV_PATH    = "yt_counterstrike.csv"
STATE_PATH  = "yt_counterstrike_state.json"

# ---- Backoff settings ----
BASE_SLEEP, MAX_SLEEP = 0.25, 16.0

# ====== Tokens & refresh helpers ======
def load_tokens() -> Dict:
    if not Path(TOKENS_PATH).exists():
        raise RuntimeError("tokens.json not found. Run oauth_flow.py first.")
    with open(TOKENS_PATH, "r") as f:
        return json.load(f)

def save_tokens(tokens: Dict) -> None:
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)

def refresh_access_token(tokens: Dict) -> Dict:
    if "refresh_token" not in tokens:
        raise RuntimeError("No refresh_token present. Re-run oauth_flow.py with prompt=consent.")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=30)
    r.raise_for_status()
    new_tokens = r.json()
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    return new_tokens

class TokenManager:
    def __init__(self):
        self.tokens = load_tokens()
        now = time.time()
        self.expiry_ts = now + float(self.tokens.get("expires_in", 0)) - 30

    def header(self) -> Dict[str, str]:
        now = time.time()
        if now >= self.expiry_ts and self.tokens.get("refresh_token"):
            self._do_refresh()
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def _do_refresh(self):
        new_tokens = refresh_access_token(self.tokens)
        self.tokens.update(new_tokens)
        save_tokens(self.tokens)
        self.expiry_ts = time.time() + float(self.tokens.get("expires_in", 0)) - 30

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

tm = TokenManager()

# ====== CSV & state ======
FIELDS = [
    "videoId","publishedAt","channelId","channelTitle","title","description",
    "viewCount","likeCount","commentCount","favoriteCount","categoryId"
]

def ensure_csv(path: str):
    if not Path(path).exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()

def load_state(path: str):
    if Path(path).exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"nextPageToken": None, "collected": 0}

def save_state(path: str, state: Dict):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)

ensure_csv(CSV_PATH)
state = load_state(STATE_PATH)
collected = int(state.get("collected", 0))
next_page = state.get("nextPageToken")
print(f"Resuming: collected={collected}, nextPageToken={next_page}")

session = requests.Session()
sleep_s = BASE_SLEEP

while collected < TARGET:
    # ---- search.list ----
    params_search = {
        "part": "id",
        "q": QUERY,
        "type": "video",
        "maxResults": BATCH_SIZE,
        "order": ORDER,
        "regionCode": "US",
    }
    if next_page:
        params_search["pageToken"] = next_page

    r = tm.request("GET", SEARCH_URL, params=params_search, timeout=30)

    if r.status_code in (403, 429, 500, 503):
        print(f"search.list {r.status_code}; backing off {sleep_s:.2f}s")
        time.sleep(sleep_s); sleep_s = min(MAX_SLEEP, sleep_s * 2)
        continue
    r.raise_for_status(); sleep_s = BASE_SLEEP

    data = r.json()
    video_ids = [it["id"]["videoId"] for it in data.get("items", []) if "videoId" in it.get("id", {})]
    if not video_ids:
        print("No more results from search.list; stopping.")
        break

    # ---- videos.list ----
    params_videos = {
        "part": "snippet,statistics",
        "id": ",".join(video_ids),
        "maxResults": BATCH_SIZE,
    }
    r2 = tm.request("GET", VIDEOS_URL, params=params_videos, timeout=30)

    if r2.status_code in (403, 429, 500, 503):
        print(f"videos.list {r2.status_code}; backing off {sleep_s:.2f}s")
        time.sleep(sleep_s); sleep_s = min(MAX_SLEEP, sleep_s * 2)
        continue
    r2.raise_for_status(); sleep_s = BASE_SLEEP

    items = r2.json().get("items", [])
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        for it in items:
            snip = it.get("snippet", {})
            stats = it.get("statistics", {})
            w.writerow({
                "videoId": it.get("id"),
                "publishedAt": snip.get("publishedAt"),
                "channelId": snip.get("channelId"),
                "channelTitle": snip.get("channelTitle"),
                "title": snip.get("title"),
                "description": snip.get("description"),
                "viewCount": stats.get("viewCount"),
                "likeCount": stats.get("likeCount"),
                "commentCount": stats.get("commentCount"),
                "favoriteCount": stats.get("favoriteCount"),
                "categoryId": snip.get("categoryId"),
            })

    collected += len(video_ids)
    next_page = data.get("nextPageToken")

    state.update({"collected": collected, "nextPageToken": next_page})
    save_state(STATE_PATH, state)

    print(f"Collected {collected} … nextPageToken={next_page}")

    if not next_page:
        print("Reached end of pagination for this query.")
        break

    time.sleep(0.1)

print(f"Done. CSV: {CSV_PATH} | State: {STATE_PATH}")
