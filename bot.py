import os
import logging
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from src.steam import SteamCache
from src.commands import GameCommands

load_dotenv()


# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gamebot")

# Add debug logging
logger.info("Checking environment variables...")
logger.info(f"DISCORD_BOT_TOKEN exists: {bool(os.getenv('DISCORD_BOT_TOKEN'))}")  # Changed from DISCORD_BOT_TOKEN
logger.info(f"STEAM_API_KEY exists: {bool(os.getenv('STEAM_API_KEY'))}")
logger.info(f"STEAM_USER_ID exists: {bool(os.getenv('STEAM_USER_ID'))}")

# Configuration
TOKEN = os.getenv("GAMEBOT_BOT_TOKEN")  # Changed from DISCORD_BOT_TOKEN
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_USER_ID = os.getenv("STEAM_USER_ID")  # Changed to match .env file

# Initialize services
steam = SteamCache(STEAM_API_KEY, STEAM_USER_ID)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Register commands
commands = GameCommands(bot, steam)

@bot.event
async def on_ready():
    """Called when bot is ready and connected to Discord."""
    logger.info(f"Logged in as {bot.user.name}")
    logger.info("Syncing commands...")
    await bot.tree.sync()
    logger.info("Commands synced!")

async def main():
    """Main async entry point."""
    try:
        if steam.is_cache_stale():
            logger.info("Cache is stale, updating...")
            steam.update_cache()
        else:
            logger.info("Using cached game data.")
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
            await bot.close()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        logger.info("Shutdown complete!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode
        cache = steam.load_cache()
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
