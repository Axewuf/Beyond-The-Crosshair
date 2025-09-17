from pathlib import Path
from src.youtube.scraper import scrape

# figure out project root = parent of /scripts
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

CSV_PATH = ASSETS / "yt_counter_strike.csv"
STATE_PATH = ASSETS / "yt_counter_strike_state.json"
TOKENS_PATH = ROOT / "data" / "tokens.json"

scrape(
    query="counter strike",
    order="viewCount",
    target=200_000,
    batch_size=50,
    csv_path=CSV_PATH,
    state_path=STATE_PATH,
    tokens_path=TOKENS_PATH,
    # client_id="YOUR_CLIENT_ID.apps.googleusercontent.com",  # optional override
    # client_secret="YOUR_CLIENT_SECRET",                     # optional override
)
