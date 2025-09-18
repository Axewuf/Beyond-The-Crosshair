from pathlib import Path
import sys

# make repo root importable so "src" works no matter where you run from
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.youtube.scraper import scrape_4mo_top50

ASSETS = ROOT / "assets"; ASSETS.mkdir(parents=True, exist_ok=True)

scrape_4mo_top50(
    start="2005-04",
    end="2025-08",
    query="counter strike",
    order="viewCount",
    batch_size=50,
    csv_path=ASSETS / "yt_counter_strike.csv",
    state_path=ASSETS / "yt_counter_strike_state.json",
    tokens_path=ROOT / "data" / "tokens.json",
)