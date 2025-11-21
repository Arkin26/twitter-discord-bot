# Twitter to Discord Bot - Dual Instance

## Overview
Run TWO independent Discord bots, each monitoring different Twitter accounts and posting to different Discord channels. Both use the official Twitter API v2 with full media support.

## Instance Setup

### Bot 1: @NFL Account
- **File**: `bot.py`
- **Environment**: DISCORD_CHANNEL_ID, DISCORD_BOT_TOKEN, TWITTER_BEARER_TOKEN
- **Monitors**: @NFL Twitter account
- **Posts to**: DISCORD_CHANNEL_ID

### Bot 2: @arkdesignss Account  
- **File**: `bot2.py`
- **Environment**: DISCORD_CHANNEL_ID_2, DISCORD_BOT_TOKEN, TWITTER_BEARER_TOKEN
- **Monitors**: @arkdesignss Twitter account
- **Posts to**: DISCORD_CHANNEL_ID_2

## Features (Both Instances)
✅ Official Twitter API v2 integration
✅ Images embedded in Discord
✅ Videos with preview + playable player
✅ Tweet metrics (likes, retweets)
✅ Duplicate prevention per channel
✅ Automatic 5-minute checks
✅ Manual check command (`!check`)

## Quick Setup
1. Get your secrets:
   - DISCORD_BOT_TOKEN (same bot, both instances use it)
   - DISCORD_CHANNEL_ID (for @NFL posts)
   - DISCORD_CHANNEL_ID_2 (for @arkdesignss posts)
   - TWITTER_BEARER_TOKEN (same token, both instances use it)

2. Add all secrets in Replit environment

3. Both bots run automatically in their workflows!

## Configuration
To change which Twitter accounts are monitored:
- **Bot 1**: Edit line 133 in `bot.py` - change `'NFL'` to any Twitter handle
- **Bot 2**: Edit line 133 in `bot2.py` - change `'arkdesignss'` to any Twitter handle

## Files
- `bot.py` - First Discord bot instance (monitors @NFL)
- `bot2.py` - Second Discord bot instance (monitors @arkdesignss)
- `posted_tweets.json` - Tracks Bot 1's posted tweets
- `posted_tweets2.json` - Tracks Bot 2's posted tweets (auto-created)

## Tech Stack
- Python 3.11
- discord.py
- requests (Twitter API v2)
- python-dotenv

## Latest Update - 2025-11-21
✅ Dual bot instance setup
✅ Each bot monitors different Twitter account
✅ Each bot posts to different Discord channel
✅ Shared bearer token and bot token
✅ Independent duplicate prevention per channel
