import discord
from discord.ext import commands
import os
import requests
from dotenv import load_dotenv
import time

load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_ID = os.getenv("STEAM_ID")

def get_owned_games():
    """Fetches owned Steam games and their genres."""
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&include_appinfo=true"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching games: {response.status_code}")
            return {}

        data = response.json()
        games = data["response"].get("games", [])

        # Only process first 10 games for testing
        game_list = {}
        for game in games[:10]:  # Limit to 10 games for testing
            game_name = game["name"]
            appid = game["appid"]
            genres = get_game_genres(appid)
            game_list[game_name] = {
                "appid": appid,
                "genres": genres
            }

        return game_list
    except Exception as e:
        print(f"Error in get_owned_games: {e}")
        return {}

def get_game_genres(appid):
    """Fetches genres for a specific Steam game using the Steam App Details API."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    
    try:
        response = requests.get(url)
        time.sleep(1.5)  # Rate limiting - Steam API requires delays between requests
        
        if response.status_code != 200:
            return []

        data = response.json()
        if str(appid) not in data or not data[str(appid)]["success"]:
            return []

        genres = data[str(appid)]["data"].get("genres", [])
        return [g["description"].lower() for g in genres]
    except Exception as e:
        print(f"Error fetching genres for appid {appid}: {e}")
        return []

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

if __name__ == "__main__":
    print(get_owned_games())  # For debugging, prints owned games with genres
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))