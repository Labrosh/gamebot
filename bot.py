import os
import json
import time
import random
import logging
import threading
import requests
import asyncio
import concurrent.futures
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
    """Load cached game data from file."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {"last_updated": 0, "games": {}}


def save_cache(data):
    """Save game data to cache file."""
    with cache_lock:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=4)


def is_cache_stale():
    """Check if cache is older than expiration time."""
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
    cache = load_cache()
    owned_games = fetch_owned_games()
    games_to_update = []

    for game in owned_games:
        if game["name"] not in cache["games"] or not cache["games"][game["name"]]["genres"]:
            games_to_update.append(game)

    logger.info(f"Updating {len(games_to_update)} games with missing genres...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        results = executor.map(lambda game: (game["name"], fetch_game_genres(game["appid"])), games_to_update)
        
        for name, genres in results:
            if genres:
                cache["games"][name] = {"appid": game["appid"], "genres": genres}
    
    cache["last_updated"] = time.time()
    save_cache(cache)
    logger.info("Game cache updated successfully.")


def get_cached_games():
    """Load game data from cache and return as a dictionary."""
    return load_cache().get("games", {})


@bot.command()
async def recommend(ctx, genre: str):
    """Recommend a game based on genre."""
    games = get_cached_games()
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
    if is_cache_stale():
        logger.info("Cache is stale, updating...")
        update_cache()
    else:
        logger.info("Using cached game data.")
    
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
