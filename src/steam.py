import os
import json
import time
import logging
import threading
import requests
import concurrent.futures
import shutil
from typing import Dict, List, Optional
from tqdm import tqdm
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
        params = {
            "key": self.api_key,
            "steamid": self.user_id,
            "include_appinfo": 1,
            "format": "json"
        }
        url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
        
        logger.info(f"Fetching games from Steam API...")
        try:
            response = requests.get(url, params=params)
            logger.info(f"Steam API Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "response" not in data:
                    logger.error(f"Unexpected API response format: {data}")
                    return []
                    
                games = data["response"].get("games", [])
                logger.info(f"Found {len(games)} games in API response")
                return games
            else:
                logger.error(f"Steam API error: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching games: {e}")
            return []

    REQUIRED_FIELDS = {
        "genres": {"path": ["genres"], "transform": lambda x: [g["description"].lower() for g in x]},
        "description": {"path": ["short_description"], "transform": str.strip},
        # Add new fields here like:
        # "price": {"path": ["price_overview", "final_formatted"], "transform": lambda x: x},
        # "categories": {"path": ["categories"], "transform": lambda x: [c["description"] for c in x]},
    }

    def fetch_game_details(self, appid: int) -> Dict:
        """Fetches game details from Steam API."""
        params = {
            "appids": appid,
            "cc": "us",  # Country code
            "l": "english",  # Language
            "format": "json"
        }
        url = "https://store.steampowered.com/api/appdetails"
        
        try:
            # Add delay to avoid rate limiting
            time.sleep(0.5)  # 500ms delay between requests
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json().get(str(appid), {}).get("data", {})
                if not data:
                    logger.warning(f"No data returned for game {appid}")
                    return {field: [] if field != "description" else "" for field in self.REQUIRED_FIELDS}
                    
                result = {}
                for field, config in self.REQUIRED_FIELDS.items():
                    value = data
                    for key in config["path"]:
                        value = value.get(key, {})
                    
                    if value:
                        result[field] = config["transform"](value)
                    else:
                        result[field] = "" if field == "description" else []
                        
                logger.info(f"Successfully fetched details for game {appid}")
                return result
                
            logger.warning(f"Failed to fetch details for game {appid}: Status {response.status_code}")
            return {field: [] if field != "description" else "" for field in self.REQUIRED_FIELDS}
            
        except Exception as e:
            logger.error(f"Error fetching details for game {appid}: {e}")
            return {field: [] if field != "description" else "" for field in self.REQUIRED_FIELDS}

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
        cache = self.load_cache()
        games = cache.get("games", {})
        
        # Check if any games are missing required fields
        for game_name, game_data in games.items():
            for field in self.REQUIRED_FIELDS:
                if field not in game_data:
                    logger.info(f"Game {game_name} missing field: {field}")
                    return True
                if not game_data.get(field):  # Check if field is empty
                    logger.info(f"Game {game_name} has empty {field}")
                    return True
        
        logger.info(f"Checking {len(games)} games in cache...")
        
        # Then check library changes
        if self.is_library_changed():
            return True

        logger.info("Cache appears up to date")            
        return time.time() - cache.get("last_updated", 0) > self.cache_expiration

    def fetch_game_details_batch(self, appids: List[int], batch_size: int = 10) -> Dict[int, Dict]:
        """Fetch details for multiple games in batches."""
        results = {}
        
        # Split appids into batches
        for i in range(0, len(appids), batch_size):
            batch = appids[i:i + batch_size]
            
            # Add delay between batches to avoid rate limiting
            if i > 0:
                time.sleep(1.5)  # 1.5s between batches
            
            params = {
                "appids": ",".join(map(str, batch)),
                "cc": "us",
                "l": "english",
                "format": "json"
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            try:
                response = requests.get(
                    "https://store.steampowered.com/api/appdetails",
                    params=params,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for appid in batch:
                        app_data = data.get(str(appid), {}).get("data", {})
                        result = {}
                        
                        for field, config in self.REQUIRED_FIELDS.items():
                            value = app_data
                            for key in config["path"]:
                                value = value.get(key, {})
                            
                            result[field] = config["transform"](value) if value else ("" if field == "description" else [])
                            
                        results[appid] = result
                        
                elif response.status_code == 403:
                    logger.error("Steam API rate limit hit, increasing delay")
                    time.sleep(5)  # Extra delay on rate limit
                    
            except Exception as e:
                logger.error(f"Batch request failed: {e}")
                
        return results

    def update_cache(self, force=False):
        """Updates the game cache. If 'force' is True, completely rebuilds the cache."""
        self.backup_cache()

        # If force is enabled, wipe the entire cache
        if force:
            logger.info("Force refreshing ALL games...")
            cache = {"games": {}, "last_updated": 0}  # Reset cache completely
        else:
            cache = self.load_cache()
        
        cache["library_signature"] = self.get_library_signature()

        if "failed_games" in cache:
            del cache["failed_games"]

        owned_games = self.fetch_owned_games()
        logger.info(f"Found {len(owned_games)} games in Steam library")
        
        games_to_update = []

        # First pass: Mark games needing updates
        for game in owned_games:
            game_name = game["name"]

            # If forcing or game is new/missing, update it
            if force or game_name not in cache["games"]:
                games_to_update.append(game)
            else:
                # Check for missing or empty required fields
                game_data = cache["games"][game_name]
                for field in self.REQUIRED_FIELDS:
                    if field not in game_data or not game_data[field]:
                        games_to_update.append(game)
                        break

        failed_games = []

        # Update games with progress bar
        for i in range(0, len(games_to_update), 10):
            batch = games_to_update[i:i + 10]
            batch_appids = [game["appid"] for game in batch]

            details = self.fetch_game_details_batch(batch_appids)

            for game in batch:
                name = game["name"]
                appid = game["appid"]

                game_details = details.get(appid, {})
                if game_details and (game_details["genres"] or game_details["description"]):
                    # Always update game data, ensuring missing fields are filled
                    cache["games"][name] = {
                        "appid": appid,
                        "genres": game_details.get("genres", cache["games"].get(name, {}).get("genres", [])),
                        "description": game_details.get("description", cache["games"].get(name, {}).get("description", "")),
                        "last_updated": time.time()
                    }
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
