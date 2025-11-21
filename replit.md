# Twitter to Discord Bot

## Overview
A Discord bot that monitors @NFL on Twitter/X and automatically posts new tweets to a Discord channel with rich embeds, images, and videos all in one structured message.

## Purpose
Monitor specific Twitter accounts and cross-post them to Discord using the official Twitter API v2 with full media support.

## How It Works
1. Bot connects to Discord
2. Every 5 minutes, checks @NFL for new tweets
3. For each new tweet:
   - Creates a rich embed with tweet text
   - Displays images directly in the embed
   - Shows video preview thumbnail with clickable video link
   - Includes engagement metrics (likes, retweets)
   - Posts everything in one structured message
4. Remembers posted tweets to avoid duplicates

## Features
✅ Official Twitter API v2 integration
✅ Images embedded in Discord
✅ Videos with preview + playable link in same embed
✅ Tweet metrics (likes, retweets)
✅ Duplicate prevention
✅ Automatic 5-minute checks
✅ Manual check command (`!check`)

## Setup
1. Create Discord bot: https://discord.com/developers/applications
2. Get Twitter bearer token: https://developer.twitter.com/en/portal/dashboard
3. Add secrets in Replit:
   - DISCORD_BOT_TOKEN
   - DISCORD_CHANNEL_ID
   - TWITTER_BEARER_TOKEN

## Files
- `bot.py` - Main Discord bot with Twitter API integration
- `posted_tweets.json` - Tracks posted tweets to avoid duplicates

## Tech Stack
- Python 3.11
- discord.py
- requests (Twitter API v2)
- python-dotenv

## Latest Update - 2025-11-21
✅ Clean single-file implementation
✅ Full media support (images + videos in one embed)
✅ Structured embedding with preview images and clickable video links
✅ Top 5 tweets per check for testing
