# Pairwise-at-peak heatmap via 2-term requests only (no stitching).
# For each row game i (with peak month p_i), query [i, j], then rescale so i at p_i == 100.

import time
from pathlib import Path
import pandas as pd
import numpy as np
from pytrends.request import TrendReq

GAMES = [
    "Counter-Strike","Valorant","Call of Duty","Overwatch",
    "Battlefield","PUBG","Fortnite","Apex Legends","Rainbow Six Siege",
]
TIMEFRAME = "2004-01-01 2025-12-31"  # wide; monthly resampling applied
GEO, GPROP, CAT = "", "", 0
SLEEP = 1.0

ASSETS = Path("assets")
peaks = pd.read_csv(ASSETS / "trends_peaks_single.csv")   # from your single-term run
# expect columns: game, peak_value, peak_month (YYYY-MM)
peak_map = dict(zip(peaks["game"], peaks["peak_month"]))

py = TrendReq(hl="en-US", tz=0)

def monthly_pair(term_a, term_b):
    py.build_payload([term_a, term_b], timeframe=TIMEFRAME, geo=GEO, gprop=GPROP, cat=CAT)
    df = py.interest_over_time()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.drop(columns=[c for c in df.columns if c == "isPartial"], errors="ignore")
    df.index = pd.to_datetime(df.index)
    # If weekly, average to month-start
    if len(df.index) > 1:
        gaps = df.index.to_series().diff().dt.days.dropna()
        if not gaps.empty and gaps.mode().iloc[0] <= 8:
            df = df.resample("MS").mean()
    return df[[term_a, term_b]].astype(float)

# Build matrix
rows = []
for i, gi in enumerate(GAMES):
    pi = peak_map.get(gi)
    if not pi:
        continue
    month_i = pd.to_datetime(pi + "-01")
    row_vals = {}
    for j, gj in enumerate(GAMES):
        if gi == gj:
            row_vals[gj] = 100.0
            continue
        df_pair = monthly_pair(gi, gj)
        if df_pair.empty:
            row_vals[gj] = np.nan
        else:
            # align: if exact month not present, choose nearest monthly index
            if month_i not in df_pair.index:
                # nearest index
                idx = df_pair.index.union(pd.DatetimeIndex([month_i])).sort_values().get_indexer([month_i], method="nearest")[0]
                month_use = df_pair.index[max(0, min(idx, len(df_pair.index)-1))]
            else:
                month_use = month_i

            val_i = float(df_pair.loc[month_use, gi]) if month_use in df_pair.index else np.nan
            val_j = float(df_pair.loc[month_use, gj]) if month_use in df_pair.index else np.nan

            if not np.isfinite(val_i) or val_i == 0:
                row_vals[gj] = np.nan
            else:
                # scale so gi at its peak month equals 100 in this pair
                scale = 100.0 / val_i
                row_vals[gj] = round(val_j * scale, 2)

        if j < len(GAMES) - 1:
            time.sleep(SLEEP)

    rows.append(pd.Series(row_vals, name=f"peak@{gi} ({pi})"))

pair_heat = pd.DataFrame(rows)
pair_heat.to_csv(ASSETS / "trends_heatmap_pairwise.csv")

print("Saved pairwise-at-peak heatmap → assets/trends_heatmap_pairwise.csv")
pair_heat.head()