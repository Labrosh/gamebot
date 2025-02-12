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
    """Fetches game genres and short description from Steam API."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get(str(appid), {}).get("data", {})
        return {
            "genres": [genre["description"].lower() for genre in data.get("genres", [])],
            "description": data.get("short_description", "").strip()
        }
    return {"genres": [], "description": ""}


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

        for name, appid, genres_data in results:
            if genres_data and (genres_data["genres"] or genres_data["description"]):  # Check if we got valid data
                cache["games"][name]["appid"] = appid
                cache["games"][name]["genres"] = genres_data["genres"]
                cache["games"][name]["description"] = genres_data["description"]
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

def get_all_genres():
    """Get a list of all unique genres in the library."""
    games = get_cached_games()
    genres = set()
    for game in games.values():
        genres.update(game.get("genres", []))
    return sorted(genres)

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def find_closest_genres(input_genre: str, all_genres: list[str], max_distance: int = 2) -> list[str]:
    """Find genres that are close matches to the input."""
    input_genre = input_genre.lower()
    matches = []
    
    for genre in all_genres:
        # Exact substring match gets priority
        if input_genre in genre.lower() or genre.lower() in input_genre:
            matches.append(genre)
            continue
            
        # Check Levenshtein distance for typos
        distance = levenshtein_distance(input_genre, genre.lower())
        if distance <= max_distance:
            matches.append(genre)
    
    return matches

@bot.command()
async def recommend(ctx, genre: str = None):
    """Recommend a game based on genre (or random if no genre specified)."""
    games = get_cached_games()
    
    if genre is None:
        # No genre specified, pick any game
        game_name = random.choice(list(games.keys()))
        game_data = games[game_name]
        genres = game_data["genres"]
        genre_text = f" ({', '.join(genres)})" if genres else ""
        desc = f"\n> {game_data.get('description', '')}" if game_data.get('description') else ""
        await ctx.send(f"🎮 Random game recommendation: **{game_name}**{genre_text}{desc}")
        return
    
    # Genre specified, try to find matches
    filtered_games = [name for name, data in games.items() if genre.lower() in data.get("genres", [])]
    
    if not filtered_games:
        # Get all available genres for suggestions
        all_genres = get_all_genres()
        # Find similar genres using fuzzy matching
        similar_genres = find_closest_genres(genre, all_genres)
        
        message = f"❌ No games found with genre '{genre}'."
        if similar_genres:
            message += f"\nDid you mean: {', '.join(similar_genres)}?"
        else:
            # Show some available genres if no similar ones found
            sample_genres = random.sample(all_genres, min(3, len(all_genres)))
            message += f"\nAvailable genres include: {', '.join(sample_genres)}"
        
        await ctx.send(message)
    else:
        recommended_game = random.choice(filtered_games)
        game_data = games[recommended_game]
        desc = f"\n> {game_data.get('description', '')}" if game_data.get('description') else ""
        await ctx.send(f"🎮 Recommended {genre} game: **{recommended_game}**{desc}")

@bot.command()
async def refresh(ctx):
    """Manually refresh the game cache."""
    await ctx.send("♻️ Refreshing game cache, this may take a while...")
    update_cache()
    await ctx.send("✅ Game cache updated!")

@bot.event
async def on_message(message):
    """Handle direct mentions of the bot"""
    if message.author == bot.user:  # Ignore self
        return

    # Check if bot was mentioned AND someone is asking what it does
    if bot.user in message.mentions and any(q in message.content.lower() for q in [
        "what do you do",
        "what can you do",
        "help",
        "commands",
        "how do you work"
    ]):
        help_text = "Hi! I'm GameBot! I can recommend games from your Steam library. Try `!recommend` for a random game or `!recommend action` for a specific genre! 🎮"
        await message.channel.send(help_text)
    
    await bot.process_commands(message)  # Don't forget to process other commands!

@bot.command()
async def helpgamebot(ctx):
    """Show GameBot's available commands"""
    help_text = """Here's what I can do:
• `!recommend` - Get a random game recommendation
• `!recommend [genre]` - Get a game recommendation for a specific genre
• `!refresh` - Update the game cache (admin only)
• `!helpgamebot` - Show this help message
Want more details? Just @ mention me with "what do you do"! 🎮"""
    await ctx.send(help_text)

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
