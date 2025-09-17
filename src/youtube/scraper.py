# scraper.py
# Loads tokens.json created by google_oauth.py and
# pulls paginated results from search.list, enriches with videos.list,
# auto-refreshes tokens using hardcoded CLIENT_ID/SECRET,
# and streams rows to CSV with resume support.

import csv
import json
import time
from pathlib import Path
from typing import Dict, Optional
import requests

SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"

# Root-aware defaults
ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CSV_PATH   = ASSETS_DIR / "yt_counter_strike.csv"
DEFAULT_STATE_PATH = ASSETS_DIR / "yt_counter_strike_state.json"
DEFAULT_TOKENS_PATH = ROOT / "data" / "tokens.json"

# ---- Hardcoded Google OAuth client credentials ----
CLIENT_ID     = "823344079673-gnpgl76j79rvbp0h8ne81jrke1ngs4j6.apps.googleusercontent.com"
CLIENT_SECRET = "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"

# ---- Backoff settings ----
BASE_SLEEP, MAX_SLEEP = 0.25, 16.0

FIELDS = [
    "videoId","publishedAt","channelId","channelTitle","title","description",
    "viewCount","likeCount","commentCount","favoriteCount","categoryId"
]

# -------------------- Token helpers --------------------
def _load_tokens(tokens_path: Path) -> Dict:
    if not tokens_path.exists():
        raise RuntimeError(f"{tokens_path} not found. Run scripts/google_oauth.py first.")
    return json.loads(tokens_path.read_text())

def _save_tokens(tokens_path: Path, tokens: Dict) -> None:
    tokens_path.write_text(json.dumps(tokens, indent=2))

def _refresh_access_token(tokens: Dict, client_id: str, client_secret: str) -> Dict:
    if "refresh_token" not in tokens:
        raise RuntimeError("No refresh_token present. Re-run google_oauth.py with prompt=consent.")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": client_id,
        "client_secret": client_secret,
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=30)
    r.raise_for_status()
    new_tokens = r.json()
    # Google often omits refresh_token on refresh; preserve the old one
    if "refresh_token" not in new_tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    return new_tokens

class _TokenManager:
    def __init__(self, tokens_path: Path, client_id: str, client_secret: str):
        self.tokens_path = tokens_path
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens = _load_tokens(tokens_path)
        self.expiry_ts = time.time() + float(self.tokens.get("expires_in", 0)) - 30

    def header(self) -> Dict[str, str]:
        # proactive refresh
        if time.time() >= self.expiry_ts and self.tokens.get("refresh_token"):
            self._do_refresh()
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def _do_refresh(self):
        new_tokens = _refresh_access_token(self.tokens, self.client_id, self.client_secret)
        self.tokens.update(new_tokens)
        _save_tokens(self.tokens_path, self.tokens)
        self.expiry_ts = time.time() + float(self.tokens.get("expires_in", 0)) - 30

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {}) or {}
        headers |= self.header()
        r = requests.request(method, url, headers=headers, **kwargs)
        if r.status_code == 401 and self.tokens.get("refresh_token"):
            # reactive refresh + single retry
            self._do_refresh()
            headers = kwargs.pop("headers", {}) or {}
            headers |= self.header()
            r = requests.request(method, url, headers=headers, **kwargs)
        return r

# -------------------- Public API --------------------
def scrape(
    query: str = "counter strike",
    order: str = "viewCount",
    target: int = 200_000,
    batch_size: int = 50,
    csv_path: Optional[str | Path] = None,
    state_path: Optional[str | Path] = None,
    tokens_path: Optional[str | Path] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> int:
    """
    Scrape YouTube by paging search.list and enriching with videos.list.

    Returns:
        int: total number of videos written to CSV.
    """
    # Paths
    csv_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
    state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
    tokens_path = Path(tokens_path) if tokens_path else DEFAULT_TOKENS_PATH

    # Ensure output dir exists
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # Client credentials
    client_id = client_id or CLIENT_ID
    client_secret = client_secret or CLIENT_SECRET

    # Init token manager
    tm = _TokenManager(tokens_path, client_id, client_secret)

    # Init CSV
    if not csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    # Load state
    state = json.loads(state_path.read_text()) if state_path.exists() else {"nextPageToken": None, "collected": 0}
    collected = int(state.get("collected", 0))
    next_page = state.get("nextPageToken")
    print(f"Resuming: collected={collected}, nextPageToken={next_page}")

    sleep_s = BASE_SLEEP

    while collected < target:
        # ---- search.list ----
        params_search = {
            "part": "id",
            "q": query,
            "type": "video",
            "maxResults": batch_size,
            "order": order,
        }
        if next_page:
            params_search["pageToken"] = next_page

        r = tm.request("GET", SEARCH_URL, params=params_search, timeout=30)

        if r.status_code in (403, 429, 500, 503):
            print(f"search.list {r.status_code}; backing off {sleep_s:.2f}s")
            time.sleep(sleep_s)
            sleep_s = min(MAX_SLEEP, sleep_s * 2)
            continue
        r.raise_for_status()
        sleep_s = BASE_SLEEP

        data = r.json()
        video_ids = [it["id"]["videoId"] for it in data.get("items", []) if "videoId" in it.get("id", {})]
        if not video_ids:
            print("No more results from search.list; stopping.")
            break

        # ---- videos.list ----
        params_videos = {
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "maxResults": batch_size,
        }
        r2 = tm.request("GET", VIDEOS_URL, params=params_videos, timeout=30)

        if r2.status_code in (403, 429, 500, 503):
            print(f"videos.list {r2.status_code}; backing off {sleep_s:.2f}s")
            time.sleep(sleep_s)
            sleep_s = min(MAX_SLEEP, sleep_s * 2)
            continue
        r2.raise_for_status()
        sleep_s = BASE_SLEEP

        items = r2.json().get("items", [])
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
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

        # Save state checkpoint
        state.update({"collected": collected, "nextPageToken": next_page})
        state_path.write_text(json.dumps(state, indent=2))

        print(f"Collected {collected} … nextPageToken={next_page}")

        if not next_page:
            print("Reached end of pagination for this query.")
            break

        time.sleep(0.1)

    print(f"Done. CSV: {csv_path} | State: {state_path}")
    return collected

# Optional CLI usage
if __name__ == "__main__":
    scrape()
