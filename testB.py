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

offset = 0

max_items = 500
counter = 0
igdb_shooters = []

requestURL = IGDB_api.baseURL + endpoint

while True:
    params = f"fields *; where genres = (5); sort name asc; limit: {max_items}; offset {max_items*counter};"
    print(f"Page {counter}")
    igdb_data = requests.post(requestURL, headers = IGDB_api.authHeader, data=params)
    igdb_data = igdb_data.json()
    # print(f"igdb_data = {igdb_data}")
    if igdb_data == []:
        break 
    igdb_shooters += igdb_data
    counter += 1

df_igdb_shooters = pd.DataFrame(igdb_shooters)
df_igdb_shooters.to_csv("igdb_shooters.csv", index=False)
# print(df_igdb_shooters)