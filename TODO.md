# GameBot TODO List

## Completed Cache Improvements

- [x] Keep existing data when updating cache
- [x] Add last_updated timestamp per game entry
- [x] Implement backup before cache updates
- [x] Add cache validation and error handling
- [x] Save failed API calls to retry later
- [x] Clean up old failed API calls during refresh

## Completed Improvements

### Testing Improvements

- [x] Add command-line testing interface
- [x] Separate test logic from main bot code
- [x] Implement basic test framework
- [x] Add interactive testing mode

## Immediate Priorities

- [ ] Add cache version for future schema changes
- [ ] Implement incremental updates for game libraries
- [ ] Add Steam API check for library changes before full refresh

## Priority Fixes

- [ ] Improve cache system
  - [ ] Add partial cache updates
  - [ ] Implement lazy loading for game details
  - [ ] Add priority caching system

## Core Setup

- [x] Create repo
- [x] Set up `README.md`
- [x] Add `.gitignore`
- [x] Create `bot.py`
- [x] Connect bot to Discord
- [x] Implement basic game recommendations
- [x] Add caching system
- [x] Add multi-threading support
- [x] Implement logging

## Features to Implement

### Basic Commands

- [x] `!recommend [genre]` - Genre-based game suggestions
- [ ] `!randomgame` - Pick random game
- [ ] `!game [title]` - Show game details
- [ ] `!onsale` - Find games on sale

### Analytics & Stats

- [ ] `!stats` - Show library statistics
  - Total games owned
  - Top 5 genres
  - Most common tags
  - Total library value

### Advanced Recommendations

- [ ] `!similar [game]` - Find similar games
- [ ] `!mood [happy/scary/chill]` - Mood-based suggestions
- [ ] `!time [30/60/120]` - Games by completion time
- [ ] `!backlog` - Random unplayed game
- [ ] `!achievement` - Suggest achievable games
- [ ] `!nostalgia` - Find oldest owned game

### Multiplayer & Social

- [ ] `!compare @friend` - Compare Steam libraries
- [ ] `!party [number]` - Find games for X players
- [ ] `!multiplayer` - List multiplayer games
- [ ] `!gamenight` - Create game voting poll
- [ ] `!schedule [game]` - Plan gaming session

### User Management

- [ ] `!link [steam_url]` - Link Discord user to Steam profile
- [ ] `!unlink` - Remove Steam profile link
- [ ] `!whoami` - Show current Steam profile
- [ ] User-specific cache management
- [ ] Multi-user recommendation system

### Genre System

- [ ] Add `!genres` command to list all available genres
- [ ] Implement genre aliases (e.g., "shooter" → "action")
- [ ] Add genre descriptions and examples
- [ ] Support multi-genre queries (e.g., "action rpg")
- [ ] Add genre statistics (most/least common)

### Cache Optimization

- [x] Keep historical game data
- [x] Add cache statistics logging
- [x] Implement smarter refresh scheduling
- [ ] Add memory usage optimization
- [ ] Implement cache compression

### Performance

- [x] Improve concurrent processing
- [x] Add progress tracking by game count
- [ ] Batch genre requests
- [ ] Implement background genre fetching

## Code Quality

- [x] Improve error handling
- [x] Implement basic test infrastructure
- [ ] Add unit tests
- [ ] Add type hints
- [ ] Create proper documentation
- [ ] Add test coverage for new features

## Known Issues

- Long initial cache build (~1 hour for 1600+ games)
- Rate limiting affects refresh speed
- Memory usage during large operations
- Single user (admin) Steam library only
- No way to compare game libraries between users
- Steam API uses specific genre names that might not match common terms
- No fuzzy matching for genre names

## Future Ideas

- [ ] AI-generated game descriptions
- [ ] Recommendation voting system
- [ ] Game recommendation database
- [ ] User preference learning
- [ ] Automated test suite for all commands
- [ ] Test mode for Discord interactions

## Requested features

"can it add a cover photo? the old, vertical kind, not the social media horizontal kind"
