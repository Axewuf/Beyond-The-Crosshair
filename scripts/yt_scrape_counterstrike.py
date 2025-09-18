from pathlib import Path
from src.youtube.scraper import scrape_4mo_top50

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"; ASSETS.mkdir(parents=True, exist_ok=True)

scrape_4mo_top50(
    start="2005-04",
    end="2025-09",
    query="counter strike",
    order="viewCount",
    batch_size=50,
    csv_path=ASSETS / "yt_counter_strike.csv",
    state_path=ASSETS / "yt_counter_strike_state.json",
    tokens_path=ROOT / "data" / "tokens.json",
)