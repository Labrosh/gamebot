import discord
from discord.ext import commands
import os
import requests
from dotenv import load_dotenv

load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_ID = os.getenv("STEAM_ID")

def get_owned_games():
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&include_appinfo=true"

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        games = data['response'].get("games",[])
        return [game['name'] for game in games] # return a list of game names
    else:
        print(f"Error fetchinggames: {response.status_code}")
        return []
    


# Load bot token
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Run the bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_BOT_TOKEN not found. Set it as an environment variable.")