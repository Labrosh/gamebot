import os
import json
import time
import logging
import threading
import requests
import concurrent.futures
import shutil
from typing import Dict, List, Optional
from . import utils  # Add utils import

logger = logging.getLogger("gamebot")

class SteamCache:
    def __init__(self, steam_api_key: str, steam_user_id: str, cache_file: str = "games_cache.json"):
        self.api_key = steam_api_key
        self.user_id = steam_user_id
        self.cache_file = cache_file
        self.cache_lock = threading.Lock()
        self.cache_expiration = 24 * 60 * 60  # 24 hours
        self.concurrent_workers = 4
    
    def load_cache(self) -> Dict:
        """Load cached game data from file and validate it."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                
                if "last_updated" not in data or "games" not in data:
                    raise ValueError("Cache file is missing required keys.")
                
                return data
            
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Cache file is corrupted: {e}. Loading fresh cache.")
                return {"last_updated": 0, "games": {}}
            
        return {"last_updated": 0, "games": {}}

    def save_cache(self, data: Dict):
        """Save game data to cache file."""
        with self.cache_lock:
            with open(self.cache_file, "w") as f:
                json.dump(data, f, indent=4)

    def backup_cache(self):
        """Create a backup of the cache before modifying it."""
        if os.path.exists(self.cache_file):
            shutil.copy(self.cache_file, f"{self.cache_file}.bak")
            logger.info("Cache backup created")

    def fetch_owned_games(self) -> List[Dict]:
        """Fetches owned games from Steam API."""
        url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={self.api_key}&steamid={self.user_id}&include_appinfo=true"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("response", {}).get("games", [])
        return []

    def fetch_game_details(self, appid: int) -> Dict:
        """Fetches game genres and description from Steam API."""
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json().get(str(appid), {}).get("data", {})
            return {
                "genres": [genre["description"].lower() for genre in data.get("genres", [])],
                "description": data.get("short_description", "").strip()
            }
        return {"genres": [], "description": ""}

    def get_library_signature(self) -> Dict:
        """Get a quick signature of the Steam library state."""
        games = self.fetch_owned_games()
        game_ids = sorted([g["appid"] for g in games])
        return {
            "count": len(games),
            "ids": game_ids,
            "hash": hash(tuple(game_ids))
        }

    def is_library_changed(self) -> bool:
        """Quick check if Steam library has changed."""
        cache = self.load_cache()
        current = self.get_library_signature()
        
        cached = cache.get("library_signature", {})
        if not cached:
            return True
            
        if current["count"] != cached.get("count", 0):
            logger.info("Game count changed")
            return True
            
        if current["hash"] != cached.get("hash", 0):
            logger.info("Game list changed")
            return True
            
        return False

    def is_cache_stale(self) -> bool:
        """Check if cache needs updating."""
        if self.is_library_changed():
            return True
        cache = self.load_cache()
        return time.time() - cache.get("last_updated", 0) > self.cache_expiration

    def update_cache(self):
        """Updates the game cache with fresh data."""
        self.backup_cache()
        cache = self.load_cache()
        cache["library_signature"] = self.get_library_signature()
        
        if "failed_games" in cache:
            del cache["failed_games"]
        
        owned_games = self.fetch_owned_games()
        games_to_update = []

        for game in owned_games:
            game_name = game["name"]
            if game_name not in cache["games"]:
                cache["games"][game_name] = {"appid": game["appid"], "genres": [], "last_updated": 0}

            last_updated = cache["games"][game_name].get("last_updated", 0)
            if not cache["games"][game_name]["genres"] or (time.time() - last_updated > self.cache_expiration):
                games_to_update.append(game)

        logger.info(f"Updating {len(games_to_update)} games...")
        failed_games = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_workers) as executor:
            results = executor.map(
                lambda game: (game["name"], game["appid"], self.fetch_game_details(game["appid"])), 
                games_to_update
            )

            for name, appid, details in results:
                if details["genres"] or details["description"]:
                    cache["games"][name].update({
                        "appid": appid,
                        "genres": details["genres"],
                        "description": details["description"],
                        "last_updated": time.time()
                    })
                else:
                    failed_games.append(name)

        if failed_games:
            logger.warning(f"Failed to fetch details for {len(failed_games)} games")
            cache["failed_games"] = failed_games
        
        cache["last_updated"] = time.time()
        self.save_cache(cache)
        logger.info("Cache updated successfully")

    def get_games(self) -> Dict:
        """Get all cached games."""
        return self.load_cache().get("games", {})

    def get_all_genres(self) -> List[str]:
        """Get a list of all unique genres in the library."""
        games = self.get_games()
        genres = set()
        for game in games.values():
            genres.update(game.get("genres", []))
        return sorted(genres)

    def find_closest_genres(self, input_genre: str, all_genres: List[str]) -> List[str]:
        """Find similar genres using utils module."""
        return utils.find_similar_genres(input_genre, all_genres)
