# --- Imports
import threading, json, time, webbrowser
from urllib.parse import urlencode
import requests
from flask import Flask, request

# === 1) CONFIG ===
# Replace with your own values from Google Cloud Console → APIs & Services → Credentials
CLIENT_ID = "823344079673-gnpgl76j79rvbp0h8ne81jrke1ngs4j6.apps.googleusercontent.com"
CLIENT_SECRET = "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"

# The redirect URI must exactly match what you register in Google Cloud Console
REDIRECT_URI = "http://localhost:8080/callback"

# Example scope: read-only access to YouTube
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# OAuth endpoints
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Where to persist tokens (optional)
TOKENS_PATH = "tokens.json"   # <-- will be created/overwritten

# ====== Flask callback ======
app = Flask(__name__)
oauth_state = {"code": None, "error": None}
auth_event = threading.Event()

@app.route("/callback")
def oauth_callback():
    error = request.args.get("error")
    code = request.args.get("code")

    if error:
        oauth_state["error"] = error
        auth_event.set()
        return f"OAuth error: {error}", 400

    if not code:
        return "No code found in the request.", 400

    oauth_state["code"] = code
    auth_event.set()
    return (
        "<h2>Authorization code received ✅</h2>"
        "<p>You can close this tab and return to the app.</p>",
        200,
    )

def run_flask():
    app.run(host="0.0.0.0", port=8080, threaded=True)

# def refresh_access_token(refresh_token: str):
#     payload = {
#         "grant_type": "refresh_token",
#         "refresh_token": refresh_token,
#         "client_id": CLIENT_ID,
#         "client_secret": CLIENT_SECRET,
#     }
#     r = requests.post(TOKEN_URL, data=payload, timeout=30)
#     r.raise_for_status()
#     return r.json()

def main():
    # Start Flask in background
    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # Build auth link and open
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",        # ask for refresh_token
        "include_granted_scopes": "true",
        "prompt": "consent",             # force consent so we get refresh_token
        "state": "notebook-demo",
    }
    auth_link = f"{AUTH_URL}?{urlencode(auth_params)}"
    print("Open this URL if your browser didn't open automatically:\n", auth_link)
    try:
        webbrowser.open(auth_link)
    except Exception:
        pass

    print("Waiting for Google to redirect back to:", REDIRECT_URI)
    auth_event.wait(timeout=300)  # wait up to 5 minutes

    if oauth_state["error"]:
        raise RuntimeError(f"OAuth error from Google: {oauth_state['error']}")
    if not oauth_state["code"]:
        raise TimeoutError("Did not receive an authorization code.")

    print("Authorization code received. Exchanging for tokens...")

    token_payload = {
        "grant_type": "authorization_code",
        "code": oauth_state["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    token_res = requests.post(TOKEN_URL, data=token_payload, timeout=30)
    token_res.raise_for_status()
    tokens = token_res.json()

    # Persist tokens for reuse by yt_scraper.py
    # IMPORTANT: tokens.json contains sensitive credentials – keep it private.
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)

    print("Saved tokens to tokens.json")
    print({k: tokens.get(k) for k in ["access_token", "expires_in", "refresh_token", "token_type"]})

if __name__ == "__main__":
    main()