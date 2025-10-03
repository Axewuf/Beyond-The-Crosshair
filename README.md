# Beyond The Crosshair  

This repository contains the full data pipeline, cleaning workflows, and visualization notebooks for analyzing the Counter-Strike player base in the context of streaming trends, competitor titles, and major global events.  

---

## Requirements  

All dependencies are listed in **`requirements.txt`**. To set up your environment:  

```bash
pip install -r requirements.txt
```  

Key packages include:  
- `pandas`, `numpy` — data handling and manipulation  
- `scipy` — statistical functions (correlations, regressions)  
- `altair` — interactive visualization  
- `requests`, `json` — API calls  
- `jupyter` — notebook execution  

---

## Repository Structure  

```
├── assets/
│   ├── raw/      # unprocessed CSVs from APIs, SteamDB copy-pastes, tracker.gg tables
│   └── clean/    # cleaned and standardized CSVs written by notebooks
├── notebooks/    # cleaning & data manipulation notebooks
│   └── BeyondTheCrosshair.ipynb   # main analysis & visualization notebook
├── scripts/      # small scripts for API pulls, utility workflows
├── src/          # modularized functions for reuse across scripts/notebooks
├── requirements.txt
└── README.md
```  

---

## Data Collection  

- **API Pulls**  
  - Code in `/scripts` and `/src` handles pulling data from APIs (YouTube, Twitch, etc.).  
  - Functions are written modularly in `/src`, making them reusable across multiple scripts and notebooks.  

- **Manual Tables**  
  - Some data was collected manually by copy-pasting tables:  
    - **SteamDB** — Counter-Strike and rival games player counts.  
    - **tracker.gg** — competitor game stats not available via API.  
  - These raw tables were saved as CSVs in `assets/raw/`.  

---

## Data Cleaning  

- The **`/notebooks`** folder contains notebooks used for cleaning and transforming raw datasets.  
- Each notebook:  
  - Pulls CSVs from `assets/raw/`  
  - Cleans, aligns, and standardizes the data  
  - Writes the results to `assets/clean/` as new CSVs  
- These notebooks are **independent** and can be run in any order — each one outputs a clean dataset corresponding to its source.  

---

## Main Notebook  

- **`BeyondTheCrosshair.ipynb`** is the central analysis notebook.  
- It:  
  - Loads all clean CSVs from `assets/clean/` into DataFrames  
  - Merges across data sources where necessary  
  - Computes correlations, regressions, and other statistical summaries  
  - Renders visualizations with **Altair**, including scatterplots, annotated time-series, and comparative trends.  

This notebook produces the final set of visuals and insights used for presentations.  

---

## Usage  

1. Install dependencies with `requirements.txt`.  
2. Ensure all required raw data (from APIs, SteamDB, tracker.gg) is in `assets/raw/`.  
3. Run cleaning notebooks in `/notebooks/` to generate cleaned CSVs in `assets/clean/`.  
4. Open and run `BeyondTheCrosshair.ipynb` to reproduce the final analysis and visualizations.  

---

## Notes  

- Modular functions in `/src` can be imported directly into scripts or notebooks for consistent API handling, data formatting, and plotting utilities.  
- The pipeline is designed to be flexible: raw data can be updated and cleaned again without breaking downstream steps, since all visualizations depend only on the `assets/clean/` datasets.  

---

## Future Work  

- Automating ingestion of SteamDB and tracker.gg tables currently copy-pasted.  
- Expanding API coverage to include additional competitor titles and esports platforms.  
- Extending visualizations into an interactive dashboard for broader accessibility.  
