import discord
import os

# Load bot token (you'll need to set this up later)
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Create bot instance
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Run the bot
if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_BOT_TOKEN not found. Set it as an environment variable.")