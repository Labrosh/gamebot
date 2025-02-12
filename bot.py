import discord
from discord.ext import commands
import os
import requests
from dotenv import load_dotenv
import time
import random
import json
import logging
import concurrent.futures
import asyncio
from tqdm import tqdm
import aiohttp
from ratelimit import limits, sleep_and_retry

# Add after imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_ID = os.getenv("STEAM_ID")

CACHE_FILE = "games_cache.json"
CACHE_EXPIRATION_HOURS = 24

CALLS_PER_MINUTE = 30  # Steam API rate limit
CONCURRENT_WORKERS = 25  # Balance between speed and rate limits

class GameCache:
    def __init__(self, cache_file, expiration_hours=24):
        self.cache_file = cache_file
        self.expiration_hours = expiration_hours
        self._cache = {}

    def load(self):
        """Loads cached game data if it exists and isn't expired."""
        if self._cache:  # Check memory cache first
            logger.debug("Using memory cache")
            return self._cache

        if not os.path.exists(self.cache_file):
            return None

        with open(self.cache_file, "r") as f:
            cache = json.load(f)

        last_updated = cache.get("last_updated", 0)
        if time.time() - last_updated > self.expiration_hours * 3600:
            return None

        self._cache = cache.get("games", {})
        return self._cache

    def save(self, games):
        """Saves game data to cache file with timestamp."""
        self._cache = games
        cache_data = {
            "last_updated": time.time(),
            "games": games
        }
        with open(self.cache_file, "w") as f:
            json.dump(cache_data, f, indent=4)
        logger.debug(f"Saved {len(games)} games to cache")

    def clear(self):
        """Clears both memory and file cache."""
        self._cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
            logger.info("Cache cleared")

# Initialize cache handler
cache_handler = GameCache(CACHE_FILE, CACHE_EXPIRATION_HOURS)

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=60)
def get_game_genres(appid):
    """Rate-limited genre fetching."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    
    try:
        response = requests.get(url)
        time.sleep(0.5)  # Rate limiting - Steam API requires delays between requests
        
        if response.status_code != 200:
            return []

        data = response.json()
        if str(appid) not in data or not data[str(appid)]["success"]:
            return []

        genres = data[str(appid)]["data"].get("genres", [])
        return [g["description"].lower() for g in genres]
    except Exception as e:
        logger.error(f"Error fetching genres for appid {appid}: {e}")
        return []

async def fetch_all_games():
    """Fetches initial game list from Steam API."""
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&include_appinfo=true"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                logger.error(f"Error fetching games: {response.status}")
                return []
            data = await response.json()
            return data["response"].get("games", [])

def process_game_batch(games):
    """Process a batch of games with proper rate limiting."""
    game_list = {}
    for game in tqdm(games, desc="Fetching genres"):
        try:
            game_name = game["name"]
            appid = game["appid"]
            genres = get_game_genres(appid)
            game_list[game_name] = {"appid": appid, "genres": genres}
        except Exception as e:
            logger.error(f"Error processing {game.get('name', 'Unknown')}: {e}")
    return game_list

async def get_owned_games():
    """Fetches owned Steam games and their genres using concurrent processing."""
    cached_games = cache_handler.load()
    if cached_games:
        logger.info("Using cached game data")
        return cached_games

    logger.info("Fetching fresh game data from Steam...")
    games = await fetch_all_games()
    if not games:
        return {}

    # Split games into batches for concurrent processing
    batch_size = len(games) // CONCURRENT_WORKERS
    batches = [games[i:i + batch_size] for i in range(0, len(games), batch_size)]

    game_list = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        # Process batches concurrently
        future_to_batch = {executor.submit(process_game_batch, batch): i 
                         for i, batch in enumerate(batches)}
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_batch):
            batch_num = future_to_batch[future]
            try:
                results = future.result()
                game_list.update(results)
                logger.info(f"Completed batch {batch_num + 1}/{len(batches)}")
            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")

    cache_handler.save(game_list)
    return game_list

intents = discord.Intents.default()
intents.message_content = True  # ✅ Allows bot to read command messages

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")

@bot.command()
async def recommend(ctx, genre: str):
    """Recommends a game from the user's Steam library based on genre."""
    genre = genre.lower()
    games = await get_owned_games()

    matching_games = [game for game, details in games.items() if genre in details["genres"]]

    if matching_games:
        chosen_game = random.choice(matching_games)
        await ctx.send(f"🎮 Try **{chosen_game}**! It's a great {genre} game.")
    else:
        await ctx.send(f"❌ No {genre} games found in the library.")

@bot.command()
async def refresh(ctx):
    """Manually clears the cache and fetches fresh game data."""
    cache_handler.clear()
    await ctx.send("♻️ Cache cleared! Fetching fresh game data...")
    
    progress_msg = await ctx.send("🔄 Starting game data refresh...")
    
    try:
        games = await get_owned_games()
        if games:
            await progress_msg.edit(content=f"✅ Successfully loaded {len(games)} games!")
        else:
            await progress_msg.edit(content="❌ Failed to refresh game data.")
    except Exception as e:
        await progress_msg.edit(content=f"❌ Error during refresh: {str(e)}")

async def setup():
    """Initial setup and game data loading."""
    games = await get_owned_games()
    logger.info(f"✅ Loaded {len(games)} games")
    return games

def main():
    """Main entry point with proper async handling."""
    # Load games first
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup())
    
    # Then run the bot
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))

if __name__ == "__main__":
    main()
