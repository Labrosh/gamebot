import os
import json
import time
import logging
import threading
import shutil
from typing import Dict, List, Optional

# Third party imports
import requests
import concurrent.futures
from tqdm import tqdm
from openai import OpenAI

# Local imports
from . import utils
from .api_logger import APILogger

logger = logging.getLogger("gamebot")

class SteamCache:
    def __init__(self, steam_api_key: str, steam_user_id: str, cache_file: str = "games_cache.json"):
        self.api_key = steam_api_key
        self.user_id = steam_user_id
        self.cache_file = cache_file
        self.cache_lock = threading.Lock()
        self.cache_expiration = 24 * 60 * 60  # 24 hours
        self.concurrent_workers = 4
        self.api_logger = APILogger()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)

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
            "include_appinfo": "1",
            "include_played_free_games": "1",
            "format": "json"
        }
        url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

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
                # Debug log to see what we're getting
                logger.info(f"First game data: {games[0] if games else 'No games'}")

                # Clean up game data to ensure we have names
                processed_games = []
                for game in games:
                    if "name" not in game:
                        # If name is missing, fetch it from the store API
                        appid = game["appid"]
                        store_url = "https://store.steampowered.com/api/appdetails"
                        store_params = {"appids": appid, "l": "english"}
                        try:
                            store_response = requests.get(store_url, params=store_params)
                            if store_response.status_code == 200:
                                store_data = store_response.json().get(str(appid), {}).get("data", {})
                                game["name"] = store_data.get("name", f"Unknown Game {appid}")
                            else:
                                game["name"] = f"Unknown Game {appid}"
                        except Exception as e:
                            logger.error(f"Error fetching name for game {appid}: {e}")
                            game["name"] = f"Unknown Game {appid}"
                        time.sleep(1)  # Rate limiting
                    processed_games.append(game)

                logger.info(f"Processed {len(processed_games)} games")
                return processed_games
            else:
                logger.error(f"Steam API error: {response.text}")
                return []

        except Exception as e:
            logger.error(f"Error fetching games: {e}")
            return []

    REQUIRED_FIELDS = {
        "genres": {"path": ["genres"], "transform": lambda x: [g["description"].lower() for g in x]},
        "description": {
            "path": ["short_description"],
            "transform": lambda x: x.strip() if x else "No description available (AI needed)",
        },
        # Add new fields here like:
        # "price": {"path": ["price_overview", "final_formatted"], "transform": lambda x: x},
        # "categories": {"path": ["categories"], "transform": lambda x: [c["description"] for c in x]},
    }

    def generate_ai_description(self, game_name: str, steam_description: str = None) -> Optional[str]:
        """Generate an AI description for a game using OpenAI's API."""
        logger.info(f"Generating AI description for: {game_name}")

        if not self.openai_api_key:
            logger.error("OpenAI API Key is missing!")
            return None

        try:
            # Build the prompt based on available information
            context = f"Original Description: {steam_description}\n" if steam_description else ""
            prompt = f"""Game: {game_name}
{context}
Create a fun, engaging 2-3 sentence description that highlights what makes this game unique and exciting.
Focus on gameplay elements and what makes it special."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a passionate gamer who loves explaining what makes games special. Keep descriptions concise, fun, and engaging."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150
            )

            # Extract the AI-generated description properly using dot notation
            description = response.choices[0].message.content
            logger.info(f"AI description generated for {game_name}")
            return description

        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return None

    def fetch_game_details(self, appid: int) -> Dict:
        """Fetches game details from Steam API."""
        params = {
            "appids": str(appid),  # Convert to string
            "cc": "us",  # Country code
            "l": "english",  # Language
            "format": "json"
        }
        url = "https://store.steampowered.com/api/appdetails"

        headers = {  # Add headers
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            # Increase delay to avoid rate limiting
            time.sleep(1.0)  # 1-second delay between requests
            response = requests.get(url, params=params, headers=headers)  # Add headers to request

            if response.status_code == 200:
                data = response.json().get(str(appid), {}).get("data", {})
                if not data:
                    # Try generating AI description with more context
                    game_name = str(appid)  # We could try to get the game name from cache if available
                    ai_description = self.generate_ai_description(game_name)
                    return {
                        "genres": ["unknown"],
                        "description": ai_description if ai_description else "No description available (AI failed)",
                        "ai_enhanced": True  # Add flag to indicate AI-generated content
                    }

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
            self.api_logger.log_api_error(
                endpoint="store.steampowered.com/api/appdetails",
                status_code=response.status_code,
                response_text=response.text,
                params=params,
                headers=headers
            )
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

    def fetch_game_details_batch(self, appids: List[int], batch_size: int = 5) -> Dict[int, Dict]:
        """Fetch details for multiple games one at a time."""
        results = {}

        # Process each game individually
        with tqdm(appids, desc="Fetching game details", unit="game") as pbar:
            for appid in pbar:
                if not isinstance(appid, int) or appid <= 0:
                    logger.warning(f"Skipping invalid AppID: {appid}")
                    results[appid] = {
                        "genres": ["unknown"],
                        "description": "No description available (invalid AppID)"
                    }
                    continue

                # Add delay between requests
                time.sleep(1.5)  # Conservative rate limiting

                params = {
                    "appids": str(appid),
                    "cc": "us",
                    "l": "english"
                }

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }

                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        response = requests.get(
                            "https://store.steampowered.com/api/appdetails",
                            params=params,
                            headers=headers,
                            timeout=10
                        )

                        if response.status_code == 200:
                            data = response.json()
                            app_data = data.get(str(appid), {})
                            success = app_data.get("success", False)
                            app_data = app_data.get("data", {}) if success else {}

                            results[appid] = {
                                "genres": [g["description"].lower() for g in app_data.get("genres", [{"description": "unknown"}])],
                                "description": app_data.get("short_description", "No description available").strip() or "No description available"
                            }
                            break  # Success, exit retry loop

                        elif response.status_code == 429:  # Rate limit
                            retry_count += 1
                            wait_time = 5 * retry_count  # Exponential backoff
                            logger.warning(f"Rate limited, waiting {wait_time}s before retry {retry_count}")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"Error {response.status_code} for appid {appid}")
                            results[appid] = {
                                "genres": ["unknown"],
                                "description": "No description available"
                            }
                            break

                    except Exception as e:
                        logger.error(f"Request failed for appid {appid}: {e}")
                        retry_count += 1
                        time.sleep(5)

                if retry_count == max_retries:
                    logger.error(f"Failed to fetch appid {appid} after {max_retries} retries")
                    results[appid] = {
                        "genres": ["unknown"],
                        "description": "No description available"
                    }

        return results

    def update_cache(self, force=False):
        """Updates the game cache. If 'force' is True, completely rebuilds the cache."""
        self.backup_cache()

        if force:
            logger.info("Force refreshing ALL games...")
            cache = {"games": {}, "last_updated": 0}
        else:
            cache = self.load_cache()

        cache["library_signature"] = self.get_library_signature()

        if "failed_games" in cache:
            del cache["failed_games"]

        owned_games = self.fetch_owned_games()
        total_games = len(owned_games)
        logger.info(f"Found {total_games} games in Steam library")

        games_to_update = []

        # First pass: Mark games needing updates
        logger.info("Analyzing which games need updates...")
        with tqdm(owned_games, desc="Checking games", unit="game") as pbar:
            for game in pbar:
                game_name = game["name"]
                pbar.set_postfix_str(f"Checking: {game_name[:30]}...")

                if force or game_name not in cache["games"]:
                    games_to_update.append(game)
                else:
                    game_data = cache["games"][game_name]
                    for field in self.REQUIRED_FIELDS:
                        if field not in game_data or not game_data[field]:
                            games_to_update.append(game)
                            break

        update_count = len(games_to_update)
        if update_count == 0:
            logger.info("No games need updating!")
            return

        logger.info(f"Updating {update_count} games...")

        # Process games in smaller chunks to save progress regularly
        chunk_size = 20
        for i in range(0, len(games_to_update), chunk_size):
            chunk = games_to_update[i:i + chunk_size]
            chunk_appids = [game["appid"] for game in chunk]

            details = self.fetch_game_details_batch(chunk_appids)

            for game in chunk:
                name = game["name"]
                appid = game["appid"]

                game_details = details.get(appid, {})
                cache["games"][name] = {
                    "appid": appid,
                    "genres": game_details.get("genres", ["unknown"]),
                    "description": game_details.get("description", "No description available"),
                    "last_updated": time.time()
                }

            # Save progress after each chunk
            self.save_cache(cache)
            logger.info(f"Progress saved ({i + len(chunk)}/{len(games_to_update)} games processed)")

        cache["last_updated"] = time.time()
        self.save_cache(cache)
        logger.info(f"Cache update complete! Updated {update_count} games")

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

    def fetch_game_from_api(self, game_name: str) -> Optional[Dict]:
        """Search Steam API for a game by name and return its details if found."""
        url = "https://store.steampowered.com/api/appdetails"
        search_url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"

        try:
            # First get the full app list
            response = requests.get(search_url)
            if response.status_code != 200:
                logger.error(f"Steam API error: {response.text}")
                return None

            data = response.json().get("applist", {}).get("apps", [])

            # Find exact or very close matches only
            potential_matches = []
            search_term = game_name.lower().strip()

            for game in data:
                game_title = game["name"].lower().strip()
                # Only accept exact matches or very close matches
                if (game_title == search_term or  # Exact match
                    (len(search_term) > 4 and search_term in game_title and  # Substring match for longer terms
                     abs(len(game_title) - len(search_term)) <= 3)):  # Length difference ≤ 3
                    potential_matches.append(game)

            if not potential_matches:
                return None

            if len(potential_matches) > 1:
                logger.info(f"Multiple matches found for '{game_name}', using closest match")
                # Use the shortest name difference as it's likely the most accurate
                potential_matches.sort(key=lambda x: abs(len(x["name"]) - len(game_name)))

            # Verify the game actually exists by checking its store page
            game = potential_matches[0]
            params = {
                "appids": game["appid"],
                "cc": "us",
                "l": "english"
            }

            retry_attempts = 3
            for attempt in range(retry_attempts):
                verify_response = requests.get(url, params=params)

                if verify_response.status_code == 200:
                    break  # Success, stop retrying

                if verify_response.status_code == 429:  # Rate limit
                    logger.warning(f"Rate limited by Steam API, retrying in 5 seconds... (Attempt {attempt + 1})")
                    time.sleep(5)
                    continue

                logger.error(f"Steam API request failed with status {verify_response.status_code}")
                return None

            # Handle multiple matches
            if len(potential_matches) > 1:
                logger.info(f"Multiple matches found for '{game_name}'")
                return {
                    "multiple_matches": [
                        {"name": g["name"], "appid": g["appid"]} 
                        for g in potential_matches[:5]  # Limit to top 5
                    ]
                }

            store_data = verify_response.json().get(str(game["appid"]), {})
            if not store_data.get("success", False):
                return None

            # Get description and handle empty case
            description = store_data.get("data", {}).get("short_description", "").strip()
            if not description:
                description = "No description available (AI needed)"

            # Get genres and ensure there's always at least "Unknown"
            genres = store_data.get("data", {}).get("genres", [])
            if not genres:
                genres = [{"description": "Unknown"}]

            # Game exists, return the data
            return {
                "appid": game["appid"],
                "name": game["name"],
                "genres": [g["description"].lower() for g in genres],
                "description": description,
            }

        except Exception as e:
            logger.error(f"Error searching for game '{game_name}': {e}")
            return None

    def add_game_to_cache(self, game_name: str, game_data: Dict):
        """Add a new game to the cache and save the file."""
        cache = self.load_cache()
        cache["games"][game_name] = {
            "appid": game_data["appid"],
            "genres": game_data.get("genres", []),
            "description": game_data.get("description", "No description available"),
            "ai_description": game_data.get("ai_description", ""),  # Store AI description if available
            "last_updated": time.time()
        }

        self.save_cache(cache)
        logger.info(f"Added '{game_name}' to cache.")
