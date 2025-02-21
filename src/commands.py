import random
import logging
import os
from typing import Optional
from discord.ext import commands
from . import utils
from .steam import SteamCache

logger = logging.getLogger("gamebot")

class GameCommands:
    def __init__(self, bot: commands.Bot, steam: SteamCache):
        self.bot = bot
        self.steam = steam
        self._register_commands()

    def generate_ai_description(self, game_name: str) -> Optional[str]:
        """Generate an AI description for a game. Returns None if generation fails."""
        logger.info(f"🔍 AI description requested for: {game_name}")
        return None  # AI call will be implemented later

    def _register_commands(self):
        """Register all commands with the bot."""
        @self.bot.command()
        async def recommend(ctx, genre: str = None):
            """Recommend a game based on genre."""
            games = self.steam.get_games()
            
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
                all_genres = self.steam.get_all_genres()
                similar_genres = self.steam.find_closest_genres(genre, all_genres)
                
                message = f"❌ No games found with genre '{genre}'."
                if similar_genres:
                    message += f"\nDid you mean: {', '.join(similar_genres)}?"
                else:
                    # Use utils for genre sampling
                    sample_genres = utils.get_sample_genres(all_genres)
                    message += f"\nAvailable genres include: {', '.join(sample_genres)}"
                
                await ctx.send(message)
            else:
                recommended_game = random.choice(filtered_games)
                game_data = games[recommended_game]
                desc = f"\n> {game_data.get('description', '')}" if game_data.get('description') else ""
                await ctx.send(f"🎮 Recommended {genre} game: **{recommended_game}**{desc}")

        @self.bot.command()
        async def refresh(ctx, force: str = None):
            """Manually refresh the game cache. Use '!refresh force' to force a full rebuild."""
            if force == "force":
                await ctx.send("💣 Forcing full cache rebuild. This will take longer...")
                self.steam.update_cache(force=True)
            else:
                await ctx.send("♻️ Refreshing game cache (updating missing data only)...")
                self.steam.update_cache()

            await ctx.send("✅ Game cache updated!")

        @self.bot.command()
        async def nukeandrefresh(ctx):
            """Delete cache and force a complete refresh."""
            await ctx.send("💣 Deleting cache and forcing complete refresh...")
            if os.path.exists(self.steam.cache_file):
                self.steam.backup_cache()  # Make a backup just in case
                os.remove(self.steam.cache_file)
                logger.info("Cache file deleted")
            self.steam.update_cache()
            await ctx.send("✅ Cache completely rebuilt!")

        @self.bot.command()
        async def helpgamebot(ctx):
            """Show GameBot's available commands"""
            help_text = """Here's what I can do:
• `!recommend` - Get a random game recommendation
• `!recommend [genre]` - Get a game recommendation for a specific genre
• `!refresh` - Update the game cache (admin only)
• `!nukeandrefresh` - Delete cache and force a complete refresh (admin only)
• `!helpgamebot` - Show this help message
Want more details? Just @ mention me with "what do you do"! 🎮"""
            await ctx.send(help_text)

        @self.bot.command()
        async def info(ctx, mode: Optional[str] = None, *, game_name: str = None):
            """Show information about a specific game.
            Usage: 
                !info <game_name>     - Show basic game info
                !info ai <game_name>  - Show AI-enhanced description
            """
            # Handle the case where user types "!info ai game_name"
            if mode and mode.lower() == "ai" and game_name:
                return await self.info_with_ai(ctx, game_name)
            
            # If mode exists but isn't 'ai', it's part of the game name
            if mode and game_name:
                game_name = f"{mode} {game_name}"
            elif mode and not game_name:
                game_name = mode

            # Regular info command logic
            games = self.steam.get_games()
            matches = utils.find_similar_game(game_name, list(games.keys()))
            
            if not matches:
                await ctx.send(f"❌ Couldn't find any games matching '{game_name}'. If this seems wrong, try `!refresh force` to update the game cache.")
                return
            
            if len(matches) > 1:
                # Multiple matches found
                message = f"Found multiple matching games:\n"
                for i, name in enumerate(matches, 1):
                    message += f"{i}. {name}\n"
                message += "\nPlease be more specific!"
                await ctx.send(message)
                return
            
            # Single match found
            game = matches[0]
            game_data = games[game]
            genres = f"({', '.join(game_data['genres'])})" if game_data.get('genres') else ""
            
            desc = game_data.get("description", "").strip()
            if desc == "No description available":
                await ctx.send("🤔 Generating an AI description, please wait...")
                ai_desc = self.generate_ai_description(game)
                desc = ai_desc if ai_desc else "**This game is missing a description!** Try `!info ai game_name` for an AI-generated description."

            store_link = f"https://store.steampowered.com/app/{game_data['appid']}"
            message = (
                f"🎮 **{game}** {genres}\n"
                f"🔗 **[Steam Store]({store_link})**\n"
                f"{desc}"
            )
            await ctx.send(message)

        async def info_with_ai(self, ctx, game_name: str):
            """Helper method to handle AI-enhanced game descriptions."""
            games = self.steam.get_games()
            matches = utils.find_similar_game(game_name, list(games.keys()))
            
            if not matches:
                await ctx.send(f"❌ Couldn't find any games matching '{game_name}'")
                return
                
            game = matches[0]
            await ctx.send(f"🤖 Generating an enhanced AI description for **{game}**...")
            
            ai_desc = self.generate_ai_description(game)
            if ai_desc:
                message = f"🎮 **{game}**\n{ai_desc}"
                await ctx.send(message)
            else:
                await ctx.send(f"❌ Sorry, I couldn't generate an AI description for '{game}' at the moment.")

        @self.bot.event
        async def on_message(message):
            """Handle direct mentions of the bot"""
            if message.author == self.bot.user:
                return

            if self.bot.user in message.mentions and any(q in message.content.lower() for q in [
                "what do you do",
                "what can you do",
                "help",
                "commands",
                "how do you work"
            ]):
                help_text = "Hi! I'm GameBot! I can recommend games from your Steam library. Try `!recommend` for a random game or `!recommend action` for a specific genre! 🎮"
                await message.channel.send(help_text)
            
            await self.bot.process_commands(message)
