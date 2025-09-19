# scripts/igdb_fetch_shooters.py
import json
import time
from pathlib import Path
import sys
import requests
import pandas as pd

# make repo root importable so "src" works no matter where you run from
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

DATA_DIR = ROOT / "data"
TOKENS_PATH = DATA_DIR / "twitch_tokens.json"

# ====== IGDB/Twitch config ======
IGDB_BASE_URL = "https://api.igdb.com/v4/"
ENDPOINT      = "games"      # or "release_dates", etc.
GENRE_ID      = 5            # Shooter = 5
MAX_ITEMS     = 500          # IGDB max per request
OUT_CSV       = ASSETS / "igdb_games.csv"

# Optional polite pacing
SLEEP_BETWEEN_PAGES = 0.2


def load_twitch_token(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"{path} not found. Run scripts/twitch_oauth.py first to create an app token.")
    tok = json.loads(path.read_text())
    # Soft check for expiry; refresh by re-running twitch_oauth.py if expired
    if int(tok.get("expires_at", 0)) <= int(time.time()):
        raise RuntimeError("Twitch app token expired. Re-run scripts/twitch_oauth.py to refresh.")
    return tok


def build_headers(client_id: str, access_token: str) -> dict:
    return {
        "Client-ID": client_id,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def main():
    # --- 1) Load token saved by twitch_oauth.py
    tok = load_twitch_token(TOKENS_PATH)
    access_token = tok["access_token"]
    client_id    = tok["client_id"]

    headers = build_headers(client_id, access_token)
    request_url = IGDB_BASE_URL + ENDPOINT

    # --- 2) Fetch all shooter games in pages of 500 (sorted by name asc)
    counter = 0
    all_rows = []

    while True:
        # IGDB query language: https://api-docs.igdb.com/#filters
        # NOTE: correct syntax is `limit 500; offset 0;` (no colon)
        q = f"fields *; sort name asc; limit {MAX_ITEMS}; offset {MAX_ITEMS * counter};"

        print(f"Page {counter}  | offset={MAX_ITEMS * counter}")
        res = requests.post(request_url, headers=headers, data=q, timeout=30)

        if res.status_code == 429:
            # Too many requests — back off a bit
            wait = int(res.headers.get("Retry-After", "2"))
            print(f"429 rate limited. Sleeping {wait}s…")
            time.sleep(wait)
            continue

        res.raise_for_status()
        page = res.json()

        if not page:
            break

        all_rows.extend(page)
        counter += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    # --- 3) Write CSV
    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(f"Saved {len(df):,} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
