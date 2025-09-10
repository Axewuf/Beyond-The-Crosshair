import requests
import os
import time
import pandas as pd
from datetime import datetime

access_code = {
    "access_token": "kyjymututmshrl6e6yj3tcqyokuogf",
    "expires_in": 4830188,
    "token_type": "bearer"
}

class APIinfo:
    def __init__(self, baseURL = str, token = str):
        self.authHeader = {"Client-ID": "njp50qwu2nvpsx219fyqo3bzv63oin","Authorization": "Bearer "+token}
        self.baseURL = baseURL

cs_data = pd.read_csv("assets/SteamDB Counter-Strike.csv")
cs2_data = pd.read_csv("assets/SteamDB Counter-Strike 2.csv")
css_data = pd.read_csv("assets/SteamDB Counter-Strike Source.csv")
cscz_data = pd.read_csv("assets/SteamDB Counter-Strike Condition Zero.csv")


IGDB_api = APIinfo("https://api.igdb.com/v4/", "kyjymututmshrl6e6yj3tcqyokuogf")
endpoint = 'games'#"release_dates"
# Shooter genre = 5

params = "limit: 10;"


requestURL = IGDB_api.baseURL + endpoint
igdb_data = requests.post(requestURL, headers = IGDB_api.authHeader, data=params)
igdb_data = igdb_data.json()

print(igdb_data)