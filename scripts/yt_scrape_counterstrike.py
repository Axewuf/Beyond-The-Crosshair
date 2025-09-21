from pathlib import Path
from src.youtube.scraper import scrape_monthly_top50

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"; ASSETS.mkdir(parents=True, exist_ok=True)
DATA   = ROOT / "data"

CSV   = ASSETS / "yt_counter_strike_monthly_top50.csv"
STATE = ASSETS / "yt_counter_strike_monthly_state.json"

TOKS = [
    DATA / "tokens_acc1.json",
    DATA / "tokens_acc2.json"
]

scrape_monthly_top50(
    start="2005-07",          # inclusive
    end="2025-10",            # exclusive (runs through Sept 2025)
    query="counter strike",
    csv_path=CSV,
    state_path=STATE,
    tokens_paths=TOKS,        # round-robin across these accounts
    batch_size=50,
)
