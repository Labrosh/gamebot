import random
import logging
import os
from typing import Optional
from discord.ext import commands
from . import utils
from .steam import SteamCache
from .openai_service import OpenAIService

logger = logging.getLogger("gamebot")

class GameCommands:
    def __init__(self, bot: commands.Bot, steam: SteamCache):
        self.bot = bot
        self.steam = steam
        self.pending_matches = {}  # Add this dictionary to store pending matches per user
        self.pending_api_matches = {}  # New dict to track if matches are from API
        self.openai = OpenAIService()
        
        # Move base_genres to class level so all commands can use it
        self.base_genres = {
            "Action & Combat": {
                "official": ["Action", "Shooter", "Fighting"],
                "aliases": ["FPS", "Third-Person Shooter", "First-Person", "Combat", "Beat 'em up"]
            },
            "Strategy & Management": {
                "official": ["Strategy", "Tower Defense", "Turn-Based Strategy", "Real-Time Strategy", "City Builder"],
                "aliases": ["RTS", "4X", "Grand Strategy", "Tactical", "Base Building"]
            },
            "RPG & Adventure": {
                "official": ["RPG", "Adventure", "Action RPG", "JRPG", "Roguelike", "Open World"],
                "aliases": ["Role-Playing", "Dungeon Crawler", "Hack and Slash"]
            },
            "Simulation": {
                "official": ["Simulation", "Racing", "Sports", "Flying", "Life Sim"],
                "aliases": ["Flight Sim", "Driving", "Management", "Business Sim"]
            },
            "Casual & Party": {
                "official": ["Casual", "Puzzle", "Family", "Party", "Board Game", "Card Game"],
                "aliases": ["Match 3", "Hidden Object", "Mini-games"]
            },
            "Other Popular": {
                "official": ["Indie", "Horror", "Survival", "Multiplayer", "Co-op", "Online"],
                "aliases": ["Battle Royale", "PvP", "Competitive", "Team-Based"]
            }
        }
        self._register_commands()

    def generate_ai_description(self, game_name: str) -> Optional[str]:
        """Generate an AI description for a game."""
        try:
            return self.openai.generate_game_description(game_name)
        except Exception as e:
            logger.error(f"Failed to generate AI description: {e}")
            return None

    async def info_with_ai(self, ctx, game_name: str):
        """Helper method to handle AI-enhanced game descriptions."""
        games = self.steam.get_games()
        matches = utils.find_similar_game(game_name, list(games.keys()))
        
        if not matches:
            await ctx.send(f"❌ Couldn't find any games matching '{game_name}'")
            return
            
        game = matches[0]
        game_data = games[game]
        
        # Check if we already have an AI description cached
        if game_data.get("ai_description"):
            ai_desc = game_data["ai_description"]
            logger.info(f"Using cached AI description for {game}")
        else:
            await ctx.send(f"🤖 Generating an enhanced description for **{game}**...")
            original_desc = game_data.get("description", "")
            ai_desc = self.steam.generate_ai_description(game, original_desc)
            
            if ai_desc:
                # Update cache with AI description
                game_data["ai_description"] = ai_desc
                self.steam.add_game_to_cache(game, {
                    "appid": game_data["appid"],
                    "genres": game_data.get("genres", []),
                    "description": original_desc,
                    "ai_description": ai_desc
                })
        
        if ai_desc:
            store_link = f"https://store.steampowered.com/app/{game_data['appid']}"
            genres = f"({', '.join(game_data.get('genres', ['unknown']))})"
            original_desc = game_data.get("description", "No description available")
            
            message = (
                f"🎮 **{game}** {genres}\n"
                f"🔗 **[Steam Store]({store_link})**\n\n"
                f"📝 **Steam Description:**\n> {original_desc}\n\n"
                f"🎭 **Fun Version:**\n> {ai_desc}"
            )
            await ctx.send(message)
        else:
            await ctx.send(f"❌ Sorry, I couldn't generate an AI description for '{game}' at the moment.")

    def _get_genre_mapping(self):
        """Create a mapping of aliases and official names to their official genres"""
        mapping = {}
        for category in self.base_genres.values():
            for official in category["official"]:
                mapping[official.lower()] = official
                # Map each alias to its official genre
                for alias in category["aliases"]:
                    if any(alias.lower() in off.lower() or off.lower() in alias.lower() 
                          for off in category["official"]):
                        mapping[alias.lower()] = official
        return mapping

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
            
            # Get genre mapping and try to find the official genre
            genre_lower = genre.lower()
            genre_map = self._get_genre_mapping()
            
            if genre_lower in genre_map:
                official_genre = genre_map[genre_lower]
                # Look for games with either the official genre or the original input
                filtered_games = [name for name, data in games.items() 
                                if any(g.lower() == official_genre.lower() or 
                                      g.lower() == genre_lower
                                      for g in data.get("genres", []))]
            else:
                # If no mapping found, try direct match
                filtered_games = [name for name, data in games.items() 
                                if any(genre_lower in g.lower() 
                                      for g in data.get("genres", []))]
            
            if not filtered_games:
                all_genres = self.steam.get_all_genres()
                similar_genres = self.steam.find_closest_genres(genre, all_genres)
                
                message = f"❌ No games found with genre '{genre}'."
                if similar_genres:
                    message += f"\nDid you mean: {', '.join(similar_genres)}?"
                message += "\nTry `!genres` to see all available genres!"
                
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
            help_text = """🎮 **GameBot Commands**
• `!recommend` - Get a random game recommendation
• `!recommend [genre]` - Get a game recommendation for a specific genre
• `!genres` - Show all available game genres and their aliases
• `!info [game name]` - Show details about a specific game
• `!info ai [game name]` - Get an AI-enhanced description of the game
• `!refresh` - Update the game cache (admin only)
• `!refresh force` - Force a complete cache rebuild (admin only)
• `!nukeandrefresh` - Delete cache and force a complete refresh (admin only)
• `!helpgamebot` - Show this help message

💡 **Tips**:
• Not sure what genres to use? Try `!genres` to see all options!
• Game and genre searches are fuzzy - close matches will work!
• If a game isn't in your library, I'll try to find it on Steam"""
            await ctx.send(help_text)

        @self.bot.command()
        async def info(ctx, mode: Optional[str] = None, *, game_name: str = None):
            """Show information about a specific game."""
            # If the input is a number and we have pending matches for this user
            if game_name is None and mode and mode.isdigit():
                # Check if there's a pending choice for this user
                choice = int(mode) - 1
                user_id = str(ctx.message.author.id)
                pending = self.pending_matches.get(user_id, [])
                is_api_match = self.pending_api_matches.get(user_id, False)
                
                if pending and 0 <= choice < len(pending):
                    selected_game = pending[choice]
                    game_name = selected_game['name'] if isinstance(selected_game, dict) else selected_game
                    
                    if is_api_match:
                        selected_game_data = pending[choice]  # Get selected game dictionary
                        appid = selected_game_data.get("appid")

                        if not appid:
                            await ctx.send("❌ Error: Could not determine App ID for the selected game.")
                            return

                        # Fetch details using App ID instead of game name
                        steam_data = self.steam.fetch_game_details(appid)

                        if steam_data and isinstance(steam_data, dict):
                            # Store it in cache using game name and appid
                            self.steam.add_game_to_cache(selected_game_data["name"], {
                                "appid": appid,
                                "genres": steam_data.get("genres", []),
                                "description": steam_data.get("description", "No description available")
                            })

                            game_data = self.steam.get_games().get(selected_game_data["name"])
                            await ctx.send(f"✅ Added '{selected_game_data['name']}' to your game list!")
                        else:
                            await ctx.send("❌ Failed to fetch game details from Steam.")
                            return

                    # Clear pending matches for this user
                    del self.pending_matches[user_id]
                    self.pending_api_matches.pop(user_id, None)
                    
                    if is_api_match:
                        # Get full game details from Steam API
                        steam_data = self.steam.fetch_game_from_api(game_name)
                        if steam_data and isinstance(steam_data, dict) and 'appid' in steam_data:
                            # Add to cache and show info
                            self.steam.add_game_to_cache(game_name, steam_data)
                            game_data = steam_data
                            await ctx.send(f"✅ Added '{game_name}' to your game list!")
                        else:
                            await ctx.send("❌ Failed to fetch game details from Steam.")
                            return
                    else:
                        game_data = self.steam.get_games().get(game_name)
                        if not game_data:
                            await ctx.send("❌ Error: Game data not found in cache.")
                            return
                    
                    # Display game info
                    genres = f"({', '.join(game_data.get('genres', []))})" if game_data.get('genres') else ""
                    desc = game_data.get("description", "No description available").strip()
                    store_link = f"https://store.steampowered.com/app/{game_data['appid']}"
                    
                    message = (
                        f"🎮 **{game_name}** {genres}\n"
                        f"🔗 **[Steam Store]({store_link})**\n"
                        f"{desc}"
                    )
                    await ctx.send(message)
                    return
                else:
                    await ctx.send("❌ No pending game selection or invalid choice. Please try your search again.")
                    return

            # Normal command processing
            if mode and mode.lower() == "ai" and game_name:
                await self.info_with_ai(ctx, game_name)
                return
            
            if mode and game_name:
                game_name = f"{mode} {game_name}"
            elif mode and not game_name:
                game_name = mode

            games = self.steam.get_games()
            matches = utils.find_similar_game(game_name, list(games.keys()))
            
            # Check for exact match first
            exact_match = next((name for name in matches if name.lower() == game_name.lower()), None)
            if exact_match:
                matches = [exact_match]
            
            if not matches:
                await ctx.send(f"🔍 '{game_name}' isn't in your library. Checking Steam API...")
                
                steam_data = self.steam.fetch_game_from_api(game_name)
                
                if not steam_data:
                    await ctx.send(f"❌ Couldn't find '{game_name}' on Steam either.")
                    return
                
                # Handle multiple matches from Steam API
                if "multiple_matches" in steam_data:
                    matches = steam_data["multiple_matches"]
                    # Store matches for this user temporarily
                    self.pending_matches[str(ctx.message.author.id)] = matches
                    self.pending_api_matches[str(ctx.message.author.id)] = True  # Mark as API matches
                    
                    message = "Found multiple games. Please select one by number:\n"
                    for i, game in enumerate(matches, 1):
                        game_name = game['name'] if isinstance(game, dict) else game
                        message += f"{i}. {game_name}\n"
                    message += "\nType `!info <number>` to select"
                    await ctx.send(message)
                    return
                    
                # Single match from Steam API
                self.steam.add_game_to_cache(game_name, steam_data)
                await ctx.send(f"✅ Found '{game_name}' on Steam! Added to your game list.")
                matches = [game_name]

            if len(matches) > 1:
                # Store matches for this user temporarily
                self.pending_matches[str(ctx.message.author.id)] = matches
                self.pending_api_matches[str(ctx.message.author.id)] = False  # Mark as local matches
                
                message = "Found multiple matching games. Please select one by number:\n"
                for i, name in enumerate(matches, 1):
                    message += f"{i}. {name}\n"
                message += "\nType `!info <number>` to select"
                await ctx.send(message)
                return
            
            # Process single match
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

        @self.bot.command()
        async def genres(ctx):
            """List all available game genres."""
            games = self.steam.get_games()
            cached_genres = self.steam.get_all_genres()

            message = "🎯 **Steam Genre Guide**\n\n"
            message += "Here are the genres you can use with the `!recommend` command:\n\n"

            # Combine cached genres with base genres
            for category, data in self.base_genres.items():
                official_genres = set(data["official"])
                # Fix the genre matching logic
                available_genres = {g for g in cached_genres 
                                  if any(official.lower() in g.lower() 
                                        for official in official_genres)}
                
                if available_genres:
                    message += f"**{category}**\n"
                    message += f"• Official: {', '.join(sorted(available_genres))}\n"
                    message += f"• Also try: {', '.join(data['aliases'])}\n\n"

            # Find any uncategorized cached genres (fix the logic here too)
            all_base_genres = {g.lower() for data in self.base_genres.values() 
                             for g in (data["official"] + data["aliases"])}
            uncategorized = {g for g in cached_genres 
                           if not any(g.lower() in bg or bg in g.lower() 
                                    for bg in all_base_genres)}

            if uncategorized:
                message += "**Other Steam Tags**\n"
                message += ", ".join(sorted(uncategorized)) + "\n\n"

            message += "\n💡 **Tips:**\n"
            message += "• Genre matching is flexible - try common terms like 'FPS' or 'RTS'\n"
            message += "• You can use `!recommend` with any of these genres\n"
            message += "• Some games might use different genre tags than listed here"

            await ctx.send(message)

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
                help_text = """👋 Hi! I'm GameBot! Here's what I can do:

🎮 **Game Recommendations**
• `!recommend` - I'll suggest a random game from your library
• `!recommend [genre]` - I'll find a game matching your preferred genre

🔍 **Game Information**
• `!info [game]` - I'll show details about a specific game
• `!info ai [game]` - Get an AI-enhanced game description
• If the game isn't in your library, I'll search Steam for it!

💡 **Pro Tips**:
• My search is fuzzy - close matches will work!
• Not sure about genres? Just try one, I'll suggest similar ones!
• Use `!helpgamebot` for a full command list"""
                await message.channel.send(help_text)
            
            await self.bot.process_commands(message)
