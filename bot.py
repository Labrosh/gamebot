import os
import json
import time
import random
import logging
import threading
import requests
import asyncio
import concurrent.futures
import shutil
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gamebot")

# Discord setup
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_USER_ID = os.getenv("STEAM_USER_ID")
CACHE_FILE = "games_cache.json"
CACHE_EXPIRATION = 24 * 60 * 60  # 24 hours
CONCURRENT_WORKERS = 4
cache_lock = threading.Lock()

# Discord Bot setup
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Called when bot is ready and connected to Discord."""
    logger.info(f"Logged in as {bot.user.name}")
    logger.info("Syncing commands...")
    await bot.tree.sync()
    logger.info("Commands synced!")


def load_cache():
    """Load cached game data from file and validate it."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            
            # Ensure the cache contains valid structure
            if "last_updated" not in data or "games" not in data:
                raise ValueError("Cache file is missing required keys.")
            
            return data  # Return cache data if valid
        
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Cache file is corrupted: {e}. Loading fresh cache.")
            return {"last_updated": 0, "games": {}}  # Return fresh cache on error
        
    return {"last_updated": 0, "games": {}}  # Return fresh cache if file doesn't exist


def save_cache(data):
    """Save game data to cache file."""
    with cache_lock:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=4)

def backup_cache():
    """Create a backup of the cache before modifying it."""
    if os.path.exists(CACHE_FILE):
        shutil.copy(CACHE_FILE, f"{CACHE_FILE}.bak")
        logger.info("Cache backup created: games_cache.json.bak")

def get_library_signature():
    """Get a quick signature of the Steam library state."""
    games = fetch_owned_games()
    game_ids = sorted([g["appid"] for g in games])  # Sort for consistent comparison
    return {
        "count": len(games),
        "ids": game_ids,
        "hash": hash(tuple(game_ids))  # Quick way to compare lists
    }

def is_library_changed():
    """Quick check if Steam library has changed."""
    cache = load_cache()
    current = get_library_signature()
    
    # Get cached signature, if it exists
    cached = cache.get("library_signature", {})
    if not cached:
        return True  # No signature = assume changed
        
    # Quick count check first
    if current["count"] != cached.get("count", 0):
        logger.info("Game count changed, library update needed")
        return True
        
    # If counts match, compare content
    if current["hash"] != cached.get("hash", 0):
        logger.info("Game list changed, library update needed")
        return True
        
    return False

def is_cache_stale():
    """Check if cache needs updating."""
    if is_library_changed():  # Check library first
        return True
    # Only check time if library hasn't changed
    cache = load_cache()
    return time.time() - cache.get("last_updated", 0) > CACHE_EXPIRATION


def fetch_owned_games():
    """Fetches owned games from Steam API."""
    url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_USER_ID}&include_appinfo=true"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("response", {}).get("games", [])
    return []


def fetch_game_genres(appid):
    """Fetches game genres from Steam API."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get(str(appid), {}).get("data", {})
        return [genre["description"].lower() for genre in data.get("genres", [])]
    return []


def update_cache():
    """Updates the game cache by adding missing genre data."""
    backup_cache()
    cache = load_cache()
    
    # Store current library signature
    cache["library_signature"] = get_library_signature()
    
    # Renmove old failed games from cache
    if "failed_games" in cache:
        del cache["failed_games"]

    
    owned_games = fetch_owned_games()
    games_to_update = []

    for game in owned_games:
        game_name = game["name"]
        
        # Keep existing data if available
        if game_name not in cache["games"]:
            cache["games"][game_name] = {"appid": game["appid"], "genres": [], "last_updated": 0}

        # Only update games missing genres or outdated (older than CACHE_EXPIRATION)
        last_updated = cache["games"][game_name].get("last_updated", 0)
        if not cache["games"][game_name]["genres"] or (time.time() - last_updated > CACHE_EXPIRATION):
            games_to_update.append(game)

    logger.info(f"Updating {len(games_to_update)} games with missing genres...")
    
    failed_games = []  # Track failed API calls

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        results = executor.map(lambda game: (game["name"], game["appid"], fetch_game_genres(game["appid"])), games_to_update)

        for name, appid, genres in results:
            if genres:
                cache["games"][name]["appid"] = appid  # Store appid
                cache["games"][name]["genres"] = genres
                cache["games"][name]["last_updated"] = time.time()
            else:
                failed_games.append(name)  # Save for retry

    # Log failed games
    if failed_games:
        logger.warning(f"Failed to fetch genres for {len(failed_games)} games: {failed_games}")
        cache["failed_games"] = failed_games  # Save failed games to retry later
    
    cache["last_updated"] = time.time()
    save_cache(cache)
    logger.info("Game cache updated successfully.")


def get_cached_games():
    """Load game data from cache and return as a dictionary."""
    return load_cache().get("games", {})


@bot.command()
async def recommend(ctx, genre: str = None):
    """Recommend a game based on genre (or random if no genre specified)."""
    games = get_cached_games()
    
    if genre is None:
        # No genre specified, pick any game
        game_name = random.choice(list(games.keys()))
        genres = games[game_name]["genres"]
        genre_text = f" ({', '.join(genres)})" if genres else ""
        await ctx.send(f"🎮 Random game recommendation: **{game_name}**{genre_text}")
        return
    
    # Genre specified, continue with existing logic
    filtered_games = [name for name, data in games.items() if genre.lower() in data.get("genres", [])]
    
    if not filtered_games:
        await ctx.send(f"❌ No {genre} games found in the library.")
    else:
        recommended_game = random.choice(filtered_games)
        await ctx.send(f"🎮 Recommended {genre} game: **{recommended_game}**")


@bot.command()
async def refresh(ctx):
    """Manually refresh the game cache."""
    await ctx.send("♻️ Refreshing game cache, this may take a while...")
    update_cache()
    await ctx.send("✅ Game cache updated!")


async def main():
    """Main async entry point."""
    try:
        if is_cache_stale():
            logger.info("Cache is stale, updating...")
            update_cache()
        else:
            logger.info("Using cached game data.")
        
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for signal_name in ('SIGINT', 'SIGTERM'):
            loop.add_signal_handler(
                getattr(signal, signal_name),
                lambda: asyncio.create_task(cleanup())
            )
        
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await cleanup()

async def cleanup():
    """Cleanup function for graceful shutdown."""
    logger.info("Shutdown requested, cleaning up...")
    try:
        if not bot.is_closed():
            # Close the Discord websocket
            await bot.close()
        
        # Get all tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        
        # Cancel all tasks
        for task in tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Close all aiohttp connectors
        for session in bot._http._HTTPClient__session:
            await session.close()
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        logger.info("Shutdown complete!")

if __name__ == "__main__":
    import signal
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode
        cache = load_cache()
        from game_tester import GameTester
        tester = GameTester(cache)
        tester.run_interactive()
    else:
        # Normal bot mode
        try:
            asyncio.run(main())
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass  # Normal shutdown, ignore these errors
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            raise
