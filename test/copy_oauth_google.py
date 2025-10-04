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
# TOKENS_PATH = "/mnt/data/google_tokens.json"

# === 2) FLASK APP (callback) ===
app = Flask(__name__)

# Shared state to pass the auth code back to the notebook
oauth_state = {"code": None, "error": None}
auth_event = threading.Event()

@app.route("/callback")
def oauth_callback():
    error = request.args.get("error")
    code = request.args.get("code")
    state = request.args.get("state")

    if error:
        oauth_state["error"] = error
        auth_event.set()
        return f"OAuth error: {error}", 400

    if not code:
        return "No code found in the request.", 400

    oauth_state["code"] = code
    auth_event.set()

    # Friendly page telling you it's ok to close the tab
    return (
        "<h2>Authorization code received ✅</h2>"
        "<p>You can close this tab and return to the notebook.</p>",
        200,
    )

def run_flask():
    # threaded=True lets Flask handle multiple requests while running in a thread
    app.run(host="0.0.0.0", port=8080, threaded=True)

# Start Flask once (safe to re-run cell; it will fail if port already bound)
# If you get 'Address already in use', interrupt kernel or change the port.
server_thread = threading.Thread(target=run_flask, daemon=True)
try:
    server_thread.start()
    time.sleep(0.5)  # tiny delay so server starts before we open the browser
except RuntimeError:
    pass  # already running

# === 3) BUILD & OPEN THE AUTH URL ===
auth_params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": " ".join(SCOPES),
    "access_type": "offline",           # request refresh token (first consent or if force)
    "include_granted_scopes": "true",
    "prompt": "consent",                # forces consent so you reliably get a refresh_token
    "state": "notebook-demo",
}
auth_link = f"{AUTH_URL}?{urlencode(auth_params)}"
print("Open this URL if your browser didn't open automatically:\n", auth_link)
try:
    webbrowser.open(auth_link)
except:
    pass

print("Waiting for Google to redirect back to:", REDIRECT_URI)
auth_event.wait(timeout=300)  # wait up to 5 minutes for the callback

if oauth_state["error"]:
    raise RuntimeError(f"OAuth error from Google: {oauth_state['error']}")

if not oauth_state["code"]:
    raise TimeoutError("Did not receive an authorization code. Try again.")

print("Authorization code received. Exchanging for tokens...")

# === 4) EXCHANGE CODE FOR TOKENS ===
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

# # Persist tokens for reuse
# with open(TOKENS_PATH, "w") as f:
#     json.dump(tokens, f, indent=2)

# print("Access token (short-lived) and refresh token (long-lived) saved to:", TOKENS_PATH)
print({k: tokens.get(k) for k in ["access_token", "expires_in", "refresh_token", "token_type"]})

# === 5) HELPER: REFRESH ACCESS TOKEN LATER ===
def refresh_access_token(refresh_token: str):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=30)
    r.raise_for_status()
    return r.json()

# === 6) SAMPLE API CALL: YouTube Data API (list my subscriptions, first page) ===
access_token = tokens["access_token"]
headers = {"Authorization": f"Bearer {access_token}"}

# Example call (adjust to your needs). Enable the YouTube Data API v3 in Cloud Console first.
yt_url = "https://www.googleapis.com/youtube/v3/subscriptions"
params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 5}
yt_res = requests.get(yt_url, headers=headers, params=params, timeout=30)

if yt_res.status_code == 401 and tokens.get("refresh_token"):
    # Access token expired; refresh and retry once
    print("Access token expired. Refreshing…")
    new_tokens = refresh_access_token(tokens["refresh_token"])
    tokens.update(new_tokens)
    # with open(TOKENS_PATH, "w") as f:
    #     json.dump(tokens, f, indent=2)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    yt_res = requests.get(yt_url, headers=headers, params=params, timeout=30)

yt_res.raise_for_status()
print("YouTube API call success. Sample item titles:")
for item in yt_res.json().get("items", []):
    print("-", item["snippet"]["title"])
