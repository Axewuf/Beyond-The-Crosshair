# src/youtube/scraper.py
# Monthly Top-50 YouTube (by viewCount), single account, resumable.
# No google-auth libs: manual OAuth refresh to oauth2.googleapis.com/token.

from __future__ import annotations

import csv
import json
import time
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
TOKEN_URL  = "https://oauth2.googleapis.com/token"

# Default output locations
OUTDIR = Path("data/youtube")
OUTDIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = OUTDIR / "monthly_top50.csv"
STATE_PATH = OUTDIR / "state.json"
TOKENS_PATH = Path("tokens.json")

# CSV columns
FIELDS = [
    "videoId", "publishedAt", "channelId", "channelTitle", "title", "description",
    "viewCount", "likeCount", "commentCount", "favoriteCount", "categoryId",
]

# Hardcoded OAuth client (as requested). Used if tokens.json lacks these fields.
CLIENT_ID = "1022046537831-c6tsit6101ptqkcjvsb3o6k6nh0495pi.apps.googleusercontent.com"
CLIENT_SECRET = "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"

# --------- helpers ---------
def _now_ts() -> float:
    return time.time()

def _parse_expiry(expiry_str: str) -> Optional[float]:
    """Parse ISO8601 'expiry' from Google tokens.json; return epoch seconds or None."""
    try:
        # Common format: "2025-09-21T16:20:31.123456Z"
        dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return None

def _month_iter(start_ym: str, end_ym: str):
    """Yield (start_dt, end_dt, 'YYYY-MM') for each month in [start, end)."""
    cur = datetime.strptime(start_ym, "%Y-%m").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_ym, "%Y-%m").replace(tzinfo=timezone.utc)
    while cur < end:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)  # first of next month
        yield cur, nxt, cur.strftime("%Y-%m")
        cur = nxt

# --------- token manager (API key or OAuth) without google libs ---------
class TokenManager:
    """
    - API Key mode: tokens.json = {"api_key": "..."}
    - OAuth mode: tokens.json contains at least {"refresh_token": "..."} and usually "access_token".
      We refresh via POST to Google's token endpoint when missing/expired or on 401.
      We persist {'access_token', 'expires_at'} back to tokens.json (keeping other fields).
    """
    def __init__(self, token_path: Path):
        self.path = Path(token_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Token file not found: {self.path}")
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.mode = "api_key" if self.data.get("api_key") else "oauth"

        # unify client credentials
        self.client_id = self.data.get("client_id") or CLIENT_ID
        self.client_secret = self.data.get("client_secret") or CLIENT_SECRET

        # normalize expiry data
        self.expires_at = None  # epoch seconds
        if "expires_at" in self.data:
            try:
                self.expires_at = float(self.data["expires_at"])
            except Exception:
                self.expires_at = None
        elif "expiry" in self.data:
            self.expires_at = _parse_expiry(self.data["expiry"])

        # if no access token or expired, try refresh (oauth only)
        if self.mode == "oauth" and (not self.data.get("access_token") or self._needs_refresh()):
            self._refresh()

    def _needs_refresh(self, skew: int = 60) -> bool:
        """True if token missing or expires within `skew` seconds."""
        if self.mode != "oauth":
            return False
        if not self.data.get("access_token"):
            return True
        if self.expires_at is None:
            # unknown expiry -> be conservative: try using it first
            return False
        return (_now_ts() + skew) >= self.expires_at

    def _refresh(self):
        refresh_token = self.data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError(
                f"No refresh_token in {self.path}. Provide a tokens.json with a refresh_token."
            )
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        r = requests.post(TOKEN_URL, data=payload, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(
                f"Token refresh failed: {r.status_code} {r.text[:200]}"
            )
        tok = r.json()
        access_token = tok.get("access_token")
        expires_in = tok.get("expires_in")  # seconds
        if not access_token:
            raise RuntimeError("Token refresh response missing access_token")

        self.data["access_token"] = access_token
        # compute expires_at epoch seconds (minus small safety window)
        if isinstance(expires_in, (int, float)):
            self.expires_at = _now_ts() + float(expires_in) - 30
            self.data["expires_at"] = self.expires_at
        # persist back to file (preserve other fields)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        params = kwargs.pop("params", {}) or {}
        headers = kwargs.pop("headers", {}) or {}

        if self.mode == "api_key":
            params["key"] = self.data["api_key"]
            return requests.request(method, url, params=params, headers=headers, **kwargs)

        # OAuth bearer
        if self._needs_refresh():
            self._refresh()
        headers["Authorization"] = f"Bearer {self.data['access_token']}"
        resp = requests.request(method, url, params=params, headers=headers, **kwargs)

        # If unauthorized, try one forced refresh and retry once
        if resp.status_code == 401:
            self._refresh()
            headers["Authorization"] = f"Bearer {self.data['access_token']}"
            resp = requests.request(method, url, params=params, headers=headers, **kwargs)
        return resp

# --------- main scraping logic ---------
def scrape_monthly_top50(
    start: str,                    # "YYYY-MM" inclusive
    end: str,                      # "YYYY-MM" exclusive
    query: str = "counter strike",
    csv_path: Optional[Path | str] = None,
    state_path: Optional[Path | str] = None,
    tokens_path: Optional[Path | str] = None,
    batch_size: int = 50,
) -> int:
    csv_path = Path(csv_path) if csv_path else CSV_PATH
    state_path = Path(state_path) if state_path else STATE_PATH
    tokens_path = Path(tokens_path) if tokens_path else TOKENS_PATH
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    tm = TokenManager(tokens_path)

    # Ensure CSV header
    fieldnames = FIELDS + ["month"]
    if not csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    # Load state
    if state_path.exists():
        try:
            st = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            st = {}
        cursor = st.get("cursor")          # last completed month label
        written_total = int(st.get("written_total", 0))
    else:
        st, cursor, written_total = {}, None, 0

    # Iterate months
    for m_start, m_end, m_label in _month_iter(start, end):
        if cursor and m_label <= cursor:
            continue

        published_after = m_start.strftime("%Y-%m-%dT00:00:00Z")
        published_before = m_end.strftime("%Y-%m-%dT00:00:00Z")

        # search.list — top by viewCount
        params_search = {
            "part": "id",
            "q": query,
            "type": "video",
            "order": "viewCount",
            "maxResults": min(50, max(1, batch_size)),
            "publishedAfter": published_after,
            "publishedBefore": published_before,
        }
        r = tm.request("GET", SEARCH_URL, params=params_search, timeout=30)
        if r.status_code in (403, 429, 500, 503):
            time.sleep(2.0)
            r = tm.request("GET", SEARCH_URL, params=params_search, timeout=30)
        r.raise_for_status()

        video_ids = [
            it["id"]["videoId"]
            for it in r.json().get("items", [])
            if isinstance(it.get("id"), dict) and "videoId" in it["id"]
        ]

        # Even if empty, advance state so teammates resume cleanly
        if not video_ids:
            st.update({"cursor": m_label, "written_total": written_total})
            state_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
            print(f"{m_label}: no results")
            continue

        # videos.list — fetch snippet + statistics for found IDs
        params_videos = {
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "maxResults": len(video_ids),
        }
        r2 = tm.request("GET", VIDEOS_URL, params=params_videos, timeout=30)
        if r2.status_code in (403, 429, 500, 503):
            time.sleep(2.0)
            r2 = tm.request("GET", VIDEOS_URL, params=params_videos, timeout=30)
        r2.raise_for_status()
        items = r2.json().get("items", [])

        # Append rows
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            for it in items:
                snip = it.get("snippet", {}) or {}
                stats = it.get("statistics", {}) or {}
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
                    "month": m_label,
                })
                written_total += 1

        # Checkpoint state
        st.update({"cursor": m_label, "written_total": written_total})
        state_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
        print(f"{m_label}: wrote {len(items)} rows (acc total {written_total})")

    print(f"Done. Wrote {written_total} rows → {csv_path}")
    return written_total
