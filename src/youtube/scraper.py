# --- NEW: monthly top-50 (with optional multi-account rotation) ---
from itertools import cycle
from datetime import datetime, timedelta
from typing import Iterable
from pathlib import Path

def _month_iter(start_ym: str, end_ym: str) -> Iterable[tuple[datetime, datetime, str]]:
    """Yield (start_dt, end_dt, month_label 'YYYY-MM') for each month in [start, end)."""
    cur = datetime.strptime(start_ym, "%Y-%m")
    end = datetime.strptime(end_ym, "%Y-%m")
    while cur < end:
        nxt = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)  # first of next month
        yield cur, nxt, cur.strftime("%Y-%m")
        cur = nxt

def scrape_monthly_top50(
    start: str,                    # "YYYY-MM" inclusive
    end: str,                      # "YYYY-MM" exclusive
    query: str = "counter strike",
    csv_path: Optional[str | Path] = None,
    state_path: Optional[str | Path] = None,
    tokens_paths: Optional[list[str | Path]] = None,   # list of tokens.json (1–3 accounts)
    client_id: Optional[str] = None,                   # hardcoded defaults used if None
    client_secret: Optional[str] = None,
    batch_size: int = 50,           # must be 50 for "top 50"
) -> int:
    """
    For each month in [start, end), fetch search.list ordered by viewCount (maxResults=50),
    then videos.list for stats, append rows with 'month' column to CSV.
    Rotates Google accounts if multiple tokens_paths are provided.
    Returns total rows written.
    """
    # paths & dirs
    csv_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
    state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    # credentials
    client_id = client_id or CLIENT_ID
    client_secret = client_secret or CLIENT_SECRET

    # token managers (1..N)
    if tokens_paths:
        managers = [ _TokenManager(Path(p), client_id, client_secret) for p in tokens_paths ]
    else:
        managers = [ _TokenManager(DEFAULT_TOKENS_PATH, client_id, client_secret) ]
    mgr_cycle = cycle(managers)

    # init CSV header if missing (+ add month column)
    fieldnames = FIELDS + ["month"]
    if not csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()

    # resume state
    if state_path.exists():
        st = json.loads(state_path.read_text())
        cursor = st.get("cursor")  # last finished month label "YYYY-MM"
        written_total = int(st.get("written_total", 0))
    else:
        st = {}
        cursor = None
        written_total = 0

    # iterate months
    for m_start, m_end, m_label in _month_iter(start, end):
        # skip if already completed
        if cursor and m_label <= cursor:
            continue

        # build ISO times
        published_after = m_start.strftime("%Y-%m-%dT00:00:00Z")
        published_before = m_end.strftime("%Y-%m-%dT00:00:00Z")

        # round-robin account
        tm = next(mgr_cycle)

        # --- search.list (one page, top 50) ---
        params_search = {
            "part": "id",
            "q": query,
            "type": "video",
            "maxResults": min(50, batch_size),
            "order": "viewCount",
            "publishedAfter": published_after,
            "publishedBefore": published_before,
            # optional: language/region tweaks
            # "relevanceLanguage": "en",
            # "regionCode": "US",
        }
        r = tm.request("GET", SEARCH_URL, params=params_search, timeout=30)

        # basic backoff
        if r.status_code in (403, 429, 500, 503):
            time.sleep(2.0)
            r = tm.request("GET", SEARCH_URL, params=params_search, timeout=30)
        r.raise_for_status()

        data = r.json()
        video_ids = [it["id"]["videoId"] for it in data.get("items", []) if "videoId" in it.get("id", {})]
        if not video_ids:
            # nothing this month; still advance state
            st.update({"cursor": m_label, "written_total": written_total})
            state_path.write_text(json.dumps(st, indent=2))
            continue

        # --- videos.list for snippet+statistics ---
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

        # append to CSV
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
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
                    "month": m_label,
                })
                written_total += 1

        # checkpoint state after each month
        st.update({"cursor": m_label, "written_total": written_total})
        state_path.write_text(json.dumps(st, indent=2))
        print(f"{m_label}: wrote {len(items)} rows (acc total {written_total})")

    print(f"Done. Wrote {written_total} rows → {csv_path}")
    return written_total
