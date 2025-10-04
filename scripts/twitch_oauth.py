# scripts/twitch_oauth.py
# Obtain a Twitch "app access token" via client-credentials and save to data/twitch_tokens.json

import json
from pathlib import Path
import requests
from time import time

# ====== 1) CONFIG ======
# Fill these with Twitch app's credentials from https://dev.twitch.tv/console/apps
CLIENT_ID     = "njp50qwu2nvpsx219fyqo3bzv63oin"
CLIENT_SECRET = "aj984frk38246b37cmyajzixsp8avs"

# Optional scopes for app access tokens (most Helix public endpoints don't need scopes).
# Example: SCOPES = ["analytics:read:games"]
SCOPES: list[str] = []

TOKEN_URL     = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL  = "https://id.twitch.tv/oauth2/validate"

# Root-aware output location: <repo>/data/twitch_tokens.json
ROOT        = Path(__file__).resolve().parents[1]
DATA_DIR    = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TOKENS_PATH = DATA_DIR / "twitch_tokens.json"


def fetch_app_access_token(client_id: str, client_secret: str, scopes: list[str]) -> dict:
    """Exchange client credentials for an app access token."""
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    if scopes:
        params["scope"] = " ".join(scopes)

    r = requests.post(TOKEN_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()  # {'access_token': '...', 'expires_in': 12345, 'token_type': 'bearer'}
    # enrich with metadata
    issued_at = int(time())
    data["issued_at"] = issued_at
    data["expires_at"] = issued_at + int(data.get("expires_in", 0))
    data["client_id"] = client_id
    return data


def validate_token(access_token: str) -> dict:
    """Validate a token (handy sanity check). Returns {} if invalid."""
    try:
        r = requests.get(VALIDATE_URL, headers={"Authorization": f"OAuth {access_token}"}, timeout=15)
        if r.status_code != 200:
            return {}
        return r.json()
    except requests.RequestException:
        return {}


def main():
    if CLIENT_ID.startswith("YOUR_") or CLIENT_SECRET.startswith("YOUR_"):
        raise SystemExit("Set CLIENT_ID and CLIENT_SECRET at the top of this file.")

    print("Requesting Twitch app access token…")
    tokens = fetch_app_access_token(CLIENT_ID, CLIENT_SECRET, SCOPES)

    # Optional: quick validate + echo app info
    info = validate_token(tokens["access_token"])
    if info:
        print(f"Validated token for client_id={info.get('client_id')}, expires_in={info.get('expires_in')}s")

    TOKENS_PATH.write_text(json.dumps(tokens, indent=2))
    print(f"Saved Twitch token to {TOKENS_PATH}")
    # small preview
    print({k: tokens.get(k) for k in ["access_token", "expires_in", "token_type", "expires_at"]})


if __name__ == "__main__":
    main()
