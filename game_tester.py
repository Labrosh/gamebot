from typing import Dict, Optional
import random
import json

class GameTester:
    def __init__(self, cache: Dict):
        self.games = cache.get("games", {})
        self.library_signature = cache.get("library_signature", {})
    
    def recommend(self, genre: str) -> Optional[str]:
        """Test genre-based game recommendations"""
        games = [name for name, data in self.games.items() 
                if genre.lower() in data.get("genres", [])]
        return random.choice(games) if games else None

    def test_library_changes(self):
        """Test library change detection"""
        print("\nLibrary Change Detection Test")
        print("----------------------------")
        
        # Show current state
        print(f"Current game count: {self.library_signature.get('count', 0)}")
        
        # Test 1: Different count
        print("\nTest 1: Simulating added game...")
        modified_sig = dict(self.library_signature)
        modified_sig["count"] += 1
        modified_sig["ids"].append(99999)  # Fake game ID
        modified_sig["hash"] = hash(tuple(modified_sig["ids"]))
        
        print(f"Modified count: {modified_sig['count']}")
        print(f"Would trigger update: {self._compare_signatures(modified_sig)}")
        
        # Test 2: Same count, different games
        print("\nTest 2: Simulating replaced game...")
        modified_sig = dict(self.library_signature)
        modified_sig["ids"][-1] = 88888  # Replace last game ID
        modified_sig["hash"] = hash(tuple(modified_sig["ids"]))
        
        print(f"Count unchanged but games different")
        print(f"Would trigger update: {self._compare_signatures(modified_sig)}")
        
        # Test 3: No changes
        print("\nTest 3: No library changes...")
        print(f"Would trigger update: {self._compare_signatures(self.library_signature)}")

    def _compare_signatures(self, test_sig: Dict) -> bool:
        """Compare test signature with cached signature"""
        if test_sig["count"] != self.library_signature.get("count", 0):
            return True
        if test_sig["hash"] != self.library_signature.get("hash", 0):
            return True
        return False

    def run_interactive(self):
        """Run interactive test session"""
        commands = {
            "recommend": self._test_recommend,
            "library": self.test_library_changes,
            "help": lambda: print("Commands: recommend, library, quit"),
        }
        
        print("Game Tester (type 'help' for commands, 'quit' to exit)")
        while True:
            command = input("\nEnter command: ").lower()
            if command == 'quit':
                break
            
            if command in commands:
                commands[command]()
            else:
                print("Unknown command. Type 'help' for available commands")

    def _test_recommend(self):
        """Test genre recommendations"""
        genre = input("Enter genre to test: ")
        game = self.recommend(genre)
        if game:
            print(f"Would recommend: {game}")
        else:
            print(f"No {genre} games found")
