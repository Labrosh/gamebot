import random
from typing import List, Set, Optional

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def find_similar_genres(input_genre: str, available_genres: List[str], max_distance: int = 2) -> List[str]:
    """Find genres that are close matches to the input."""
    input_genre = input_genre.lower()
    matches = []
    
    for genre in available_genres:
        # Exact substring match gets priority
        if input_genre in genre.lower() or genre.lower() in input_genre:
            matches.append(genre)
            continue
            
        # Check Levenshtein distance for typos
        distance = levenshtein_distance(input_genre, genre.lower())
        if distance <= max_distance:
            matches.append(genre)
    
    return matches

def get_sample_genres(genres: List[str], count: int = 3) -> List[str]:
    """Get a random sample of genres to suggest."""
    return random.sample(genres, min(count, len(genres)))

def find_similar_game(input_name: str, game_names: List[str], max_distance: int = 3) -> List[str]:
    """Find closest matching game names. Returns list of matches."""
    input_name = input_name.lower().strip()
    matches = []

    # First try exact matches
    for name in game_names:
        if input_name == name.lower():
            return [name]  # Exact match, return immediately

    # Then try substring matches
    for name in game_names:
        # Handle common cases like "witcher3" matching "The Witcher 3"
        name_simplified = ''.join(c.lower() for c in name if c.isalnum())
        input_simplified = ''.join(c.lower() for c in input_name if c.isalnum())
        
        if input_simplified in name_simplified:
            matches.append(name)
            continue

    # If no substring matches, try Levenshtein
    if not matches:
        for name in game_names:
            distance = levenshtein_distance(input_simplified, ''.join(c.lower() for c in name if c.isalnum()))
            if distance <= max_distance:
                matches.append(name)

    return matches
