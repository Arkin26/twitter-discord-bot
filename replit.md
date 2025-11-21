# Twitter to Discord Bot

## Overview
A simple Discord bot that monitors @NFL on Twitter/X and automatically posts new tweets to a Discord channel with rich embeds and links.

## Purpose
Monitor specific Twitter accounts and cross-post them to Discord using the official Twitter API v2. No scraping, no free tiers - just clean API integration.

## Architecture
```
bot.py                 # Main Discord bot
posted_tweets.json    # Tracks posted tweets to avoid duplicates
.env                  # Environment variables
```

## How It Works
1. Bot connects to Discord
2. Every 5 minutes, checks @NFL for new tweets
3. For each new tweet:
   - Creates a rich embed with the tweet text
   - Includes the Twitter link
   - Shows metrics (likes, retweets)
   - Posts to your Discord channel
4. Remembers posted tweets to avoid duplicates

## Setup
1. Get your tokens:
   - Discord Bot Token: https://discord.com/developers/applications
   - Twitter Bearer Token: https://developer.twitter.com/en/portal/dashboard
   - Discord Channel ID: Right-click channel in Discord, copy ID

2. Add secrets in Replit:
   - DISCORD_BOT_TOKEN
   - DISCORD_CHANNEL_ID
   - TWITTER_BEARER_TOKEN

3. Run the bot!

## Commands
- `!check` - Manually check for new tweets

## Current Status
✅ Clean implementation using official Twitter API v2
✅ Discord embeds with links
✅ Duplicate prevention
✅ Automatic 5-minute checks

## Tech Stack
- Python 3.11
- discord.py - Discord bot framework
- requests - HTTP client for Twitter API
- python-dotenv - Environment variables

## Recent Update
- **2025-11-21**: Fresh start with clean implementation
  - Removed all scraping attempts
  - Using official Twitter API v2
  - Simple, focused codebase
  - Rich Discord embeds with links and metrics
