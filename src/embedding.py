import os
import json
import time
import logging
from typing import Dict, List
import openai
from dotenv import load_dotenv
from src.api_logger import setup_logger

# Load environment variables
load_dotenv()

# Setup paths and constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(PROJECT_ROOT, "games_cache.json")
MAX_RETRIES = 3
RETRY_DELAY = 20  # seconds

# Setup logging using existing system
logger = setup_logger('embedding')

# Load API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing OpenAI API Key in .env file. Please add OPENAI_API_KEY=your-key")

openai.api_key = OPENAI_API_KEY


def load_game_cache() -> Dict:
    """Load the existing game cache from JSON."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {"games": {}}


def save_game_cache(cache: Dict):
    """Save the updated game cache with embeddings."""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)


def format_game_data(game: Dict) -> str:
    """Prepare a structured text representation of a game for embedding."""
    title = game.get("name", "Unknown Game")
    description = game.get("description", "No description available.")
    genres = ", ".join(game.get("genres", []))
    
    return f"{title} is a game in the genres of {genres}. {description}"


def generate_embedding(text: str) -> List[float]:
    """Generate an embedding vector for the given text using OpenAI's API."""
    for attempt in range(MAX_RETRIES):
        try:
            response = openai.Embedding.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response["data"][0]["embedding"]
        except openai.error.RateLimitError:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Rate limit hit, waiting {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Rate limit exceeded after max retries")
                return []
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return []


def update_embeddings():
    """Generate embeddings for all games and update the cache."""
    cache = load_game_cache()
    games = cache.get("games", {})

    for game_name, game_data in games.items():
        if "embedding" in game_data:
            logger.info(f"Skipping {game_name}, embedding already exists.")
            continue
        
        logger.info(f"Generating embedding for {game_name}...")
        formatted_text = format_game_data(game_data)
        embedding = generate_embedding(formatted_text)

        if embedding:
            game_data["embedding"] = embedding
            save_game_cache(cache)
            logger.info(f"Saved embedding for {game_name}.")
        
        # Avoid rate limits (sleep for 1 second per request)
        time.sleep(1)

    logger.info("✅ All embeddings updated!")


if __name__ == "__main__":
    update_embeddings()
