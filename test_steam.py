from bot import get_owned_games

def main():
    print("Testing Steam API...")
    games = get_owned_games()
    if games:
        print("Successfully retrieved games!")
        print("\nGames and their genres:")
        for i, (game_name, details) in enumerate(games.items(), 1):
            print(f"{i}. {game_name}")
            print(f"   Genres: {', '.join(details['genres']) if details['genres'] else 'No genres found'}")
            print()
    else:
        print("No games found or error occurred")

if __name__ == "__main__":
    main()
