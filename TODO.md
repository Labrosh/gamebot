# GameBot TODO List

## Immediate Priorities
- [ ] Fix inefficient cache system:
  - [ ] Add last_updated timestamp per game
  - [ ] Check Steam API for library changes before full refresh
  - [ ] Only update games that changed or are new
  - [ ] Save failed API calls to retry later
  - [ ] Add cache version for future schema changes
  - [ ] Implement backup before cache updates

## Priority Fixes
- [ ] Improve cache system
  - [ ] Keep existing data when updating cache
  - [ ] Only update games with missing/outdated data
  - [ ] Add timestamp per game entry
  - [ ] Implement proper error handling for failed API calls

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
- [ ] Keep historical game data
- [ ] Implement incremental updates
- [ ] Add lazy loading for game details
- [ ] Create priority caching system
- [ ] Add partial cache updates
- [ ] Add cache validation
- [ ] Implement cache backup system
- [ ] Add cache statistics logging

### Performance
- [ ] Batch genre requests
- [ ] Improve concurrent processing
- [ ] Add progress tracking by game count
- [ ] Implement background genre fetching

### Code Quality
- [ ] Add unit tests
- [ ] Improve error handling
- [ ] Add type hints
- [ ] Create proper documentation

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
