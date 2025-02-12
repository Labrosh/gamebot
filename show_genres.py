import json

def get_all_genres():
    with open('games_cache.json', 'r') as f:
        data = json.load(f)
        
    all_genres = set()
    for game in data['games'].values():
        all_genres.update(game.get('genres', []))
    
    print("\nAvailable genres:")
    for genre in sorted(all_genres):
        print(f"- {genre}")

if __name__ == "__main__":
    get_all_genres()
