from typing import Dict, Optional
import random

class GameTester:
    def __init__(self, cache: Dict):
        self.games = cache.get("games", {})
    
    def recommend(self, genre: str) -> Optional[str]:
        """Test genre-based game recommendations"""
        games = [name for name, data in self.games.items() 
                if genre.lower() in data.get("genres", [])]
        return random.choice(games) if games else None

    def run_interactive(self):
        """Run interactive test session"""
        print("Game Recommendation Tester (type 'quit' to exit)")
        while True:
            genre = input("\nEnter genre to test (or 'quit'): ")
            if genre.lower() == 'quit':
                break
            
            game = self.recommend(genre)
            if game:
                print(f"Would recommend: {game}")
            else:
                print(f"No {genre} games found")
