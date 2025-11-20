# Twitter to Discord Bot

## Overview
A Python Discord bot that monitors a specific Twitter account and automatically posts new tweets with embedded videos to a designated Discord channel. Built with discord.py and snscrape (free alternative to Twitter API).

## Purpose
This bot enables real-time monitoring of Twitter accounts and automatic cross-posting to Discord, with special handling for video content to ensure videos are embedded and playable directly within Discord messages. **No Twitter API credentials required** - uses the free snscrape library instead.

## Project Architecture

### Technology Stack
- **Runtime**: Python 3.11
- **Discord Integration**: discord.py (v2.6.4)
- **Twitter Integration**: snscrape (free web scraping library)
- **Configuration**: python-dotenv for environment variables

### Project Structure
```
├── bot.py            # Main bot application with all functionality
├── .env              # Environment configuration (user-provided)
├── .env.example      # Configuration template
├── last_tweet.json   # Persistent storage for last processed tweet ID
└── README.md         # Setup instructions
```

### Key Features
1. **Free Tweet Monitoring**: Uses snscrape to monitor Twitter without API costs
2. **Video Detection**: Identifies videos in tweets (native Twitter videos and external links)
3. **Discord Embedding**: Posts tweets with rich embeds and embedded video content
4. **State Persistence**: Tracks last processed tweet to prevent duplicates
5. **Error Handling**: Comprehensive error logging and graceful degradation
6. **Simple Setup**: No Twitter API credentials needed

### Configuration
The bot requires only Discord credentials:
- Discord: Bot token and target channel ID
- Twitter: Just the username to monitor (no API keys!)
- Settings: Poll interval (default 60 seconds)

## Recent Changes
- **2025-11-20**: Initial Node.js implementation with Twitter API v2
  - Installed Node.js 20 and dependencies (discord.js, twitter-api-v2, dotenv)
  - Created modular architecture for Discord and Twitter integration
  
- **2025-11-20**: Converted to Python with free snscrape
  - Switched to Python 3.11 to use snscrape library
  - Removed Twitter API dependency (was $200/month)
  - Installed discord.py, snscrape, and python-dotenv
  - Simplified to single bot.py file
  - Updated all documentation to reflect free solution

## Current State
The bot is fully implemented and ready to run. Users need to:
1. Configure `.env` file with Discord bot token and channel ID
2. Set the Twitter username to monitor
3. Run `python bot.py` to start the bot

**No Twitter API credentials needed!**

## Dependencies
- discord.py: Discord bot API client for Python
- snscrape: Free Twitter scraping library (no API needed)
- python-dotenv: Environment variable management

## User Preferences
- Prefers free/low-cost solutions over expensive APIs
- Building a Discord bot for personal use
