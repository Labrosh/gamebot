from bot import get_owned_games

def main():
    print("Testing Steam API...")
    games = get_owned_games()
    if games:
        print("Successfully retrieved games!")
        print("\nFirst 10 games:")
        for i, game in enumerate(games[:10], 1):
            print(f"{i}. {game}")
    else:
        print("No games found or error occurred")

if __name__ == "__main__":
    main()
