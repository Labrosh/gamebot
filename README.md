# GameBot

A Discord bot that recommends games from your Steam library based on genres.

## Features
- `!recommend <genre>` - Suggests a random game from your Steam library matching the specified genre
- `!refresh` - Forces an update of the games cache from Steam API

## Setup
### Prerequisites
- Python 3.12+
- Discord.py library
- A Discord bot token with message content intent enabled
- A Steam API key
- Your Steam User ID

### Installation
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install discord.py python-dotenv requests
   ```

3. Create a `.env` file with your credentials:
   ```env
   DISCORD_BOT_TOKEN=your_discord_token
   STEAM_API_KEY=your_steam_api_key
   STEAM_USER_ID=your_steam_user_id
   ```

4. Run the bot:
   ```bash
   python bot.py
   ```

## How it Works
- The bot maintains a cache of your Steam games in `games_cache.json`
- Currently refreshes entire cache if older than 24 hours (will be optimized in future updates)
- Games are fetched from Steam API along with their genres
- Use `!recommend <genre>` to get game suggestions
- Use `!refresh` to manually update the cache (will rebuild entire cache)

## Current Limitations
- Full cache rebuild on every update
- Cache updates take a long time with large libraries
- No partial updates yet
- Steam API rate limits may affect refresh speed

## Planned Features
For a full list of upcoming features, see the [TODO.md](TODO.md) file.

## Contribution
Contributions are welcome! Feel free to submit issues or pull requests.

## License
This project is licensed under the MIT License.

## Note
Make sure your Discord bot has the "Message Content Intent" enabled in the Discord Developer Portal, or commands won't work.

