from bot import get_owned_games, CACHE_FILE
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Testing Steam API...")
    
    if os.path.exists(CACHE_FILE):
        logger.info("Cache file found")
    else:
        logger.info("No cache file - will fetch fresh data")
    
    games = get_owned_games()
    if games:
        logger.info(f"Found {len(games)} games")
        logger.debug("\nGames and their genres:")
        for i, (game_name, details) in enumerate(games.items(), 1):
            logger.debug(f"{i}. {game_name}")
            logger.debug(f"   Genres: {', '.join(details['genres']) if details['genres'] else 'No genres found'}")
    else:
        logger.error("No games found or error occurred")

if __name__ == "__main__":
    main()
