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

# params = "fields age_ratings,aggregated_rating,aggregated_rating_count,alternative_names,artworks,bundles,category,checksum,collection,collections,cover,created_at,dlcs,expanded_games,expansions,external_games,first_release_date,follows,forks,franchise,franchises,game_engines,game_localizations,game_modes,game_status,game_type,genres,hypes,involved_companies,keywords,language_supports,multiplayer_modes,name,parent_game,platforms,player_perspectives,ports,rating,rating_count,release_dates,remakes,remasters,screenshots,similar_games,slug,standalone_expansions,status,storyline,summary,tags,themes,total_rating,total_rating_count,updated_at,url,version_parent,version_title,videos,websites;"
# params = "fields checksum,created_at,name,slug,updated_at,url;"
# params = "fields *; where game = 1942 & platform = (6,48);"
params = "fields age_ratings,aggregated_rating,aggregated_rating_count,alternative_names,artworks,bundles,category,checksum,collection,collections,cover,created_at,dlcs,expanded_games,expansions,external_games,first_release_date,follows,forks,franchise,franchises,game_engines,game_localizations,game_modes,game_status,game_type,genres,hypes,involved_companies,keywords,language_supports,multiplayer_modes,name,parent_game,platforms,player_perspectives,ports,rating,rating_count,release_dates,remakes,remasters,screenshots,similar_games,slug,standalone_expansions,status,storyline,summary,tags,themes,total_rating,total_rating_count,updated_at,url,version_parent,version_title,videos,websites;"
params1 = "fields name.*, where genres=5;"
params2 = "fields name,genres; where genres = (5); sort name asc; limit 20;"
requestURL = IGDB_api.baseURL + endpoint
igdb_data = requests.post(requestURL, headers = IGDB_api.authHeader, data=params2)
igdb_data = igdb_data.json()

print(igdb_data)