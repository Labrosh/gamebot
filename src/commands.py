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
        async def refresh(ctx):
            """Manually refresh the game cache."""
            await ctx.send("♻️ Refreshing game cache, this may take a while...")
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
        async def info(ctx, *, game_name: str):
            """Show information about a specific game."""
            games = self.steam.get_games()
            
            # Try to find matching games
            matches = utils.find_similar_game(game_name, list(games.keys()))
            
            if not matches:
                await ctx.send(f"❌ Couldn't find any games matching '{game_name}'")
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
            desc = f"\n> {game_data['description']}" if game_data.get('description') else "\n> No description available"
            
            await ctx.send(f"🎮 **{game}** {genres}{desc}")

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
