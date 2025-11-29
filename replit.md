# Twitter to Discord Bot - Dual Instance

## Overview
Run TWO independent Discord bots, each monitoring different Twitter accounts and posting to different Discord channels. Both use the official Twitter API v2 with full media support.

---

## 📁 Files & What Each Does

### **bot.py** - Main Discord Bot (NFL)
- Monitors **@NFL** Twitter account
- Posts to your Discord channel (DISCORD_CHANNEL_ID)
- Fetches top 2 tweets instantly when bot starts
- Checks for new tweets every 5 minutes
- Formats tweets as beautiful FixTweet-style embeds
- Prevents duplicate posts per channel
- Commands: `!check` (manually check tweets)

### **bot2.py** - Secondary Discord Bot (arkdesignss)
- Monitors **@arkdesignss** Twitter account (easily customizable)
- Posts to second Discord channel (DISCORD_CHANNEL_ID_2)
- Same features as bot.py but independent instance
- Currently disabled (needs DISCORD_CHANNEL_ID_2 secret)

### **embed_server.py** - Web Server for Tweet Embeds
- Flask web server running on port 5000
- Generates fixtweet-style embed pages
- When Discord unfurls links from bot, shows beautiful tweet cards
- Handles all the meta tags so Discord displays previews correctly
- Not directly used by user, runs in background

### **posted_tweets.json** - Bot 1 Tracking File
- Auto-created file that tracks which tweets bot.py has already posted
- Prevents duplicate posts (same tweet posted multiple times)
- Cleared when you want to repost old tweets

### **posted_tweets2.json** - Bot 2 Tracking File
- Same as above but for bot2.py
- Independent from bot.py

### **replit.md** - Documentation
- This file! Project info, setup guide, and file descriptions

---

## 🚀 How It Works

1. **Bot starts** → Logs into Discord → Immediately fetches top 2 tweets from Twitter
2. **Tweets fetched** → Bot extracts text, metrics, images, and videos
3. **Beautiful formatting** → Tweets converted to FixTweet-style embeds
4. **Posting** → Bot sends embed links to Discord channel
5. **Every 5 minutes** → Bot checks for new tweets and repeats

---

## ⚙️ Configuration

### Change Twitter Accounts Being Monitored:
- **Bot 1**: In `bot.py` line 141, change `get_tweets('NFL')` to any Twitter handle
- **Bot 2**: In `bot2.py` line 141, change `get_tweets('arkdesignss')` to any Twitter handle

### Change How Often Bots Check:
- In `bot.py` and `bot2.py`, line 135: `@tasks.loop(minutes=5)` - change `5` to any number of minutes

---

## 🔧 Environment Secrets Required

**For Bot 1 (always needed):**
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `DISCORD_CHANNEL_ID` - Channel where @NFL tweets post
- `TWITTER_BEARER_TOKEN` - Twitter API v2 bearer token

**For Bot 2 (needed to enable it):**
- `DISCORD_CHANNEL_ID_2` - Channel where @arkdesignss tweets post
- (Uses same DISCORD_BOT_TOKEN and TWITTER_BEARER_TOKEN as Bot 1)

---

## 📊 Features

✅ Official Twitter API v2 integration (not scraping)  
✅ Videos appear inside tweet cards (FixTweet style)  
✅ Images embedded in Discord  
✅ Tweet metrics (replies, retweets, likes, views)  
✅ Automatic duplicate prevention per channel  
✅ Instant fetch on startup (with smart retry logic)  
✅ 5-minute automatic checks  
✅ Manual check command (`!check`)  
✅ Rate-limit handling (auto-retries if Twitter throttles)  

---

## 🛠️ Tech Stack

- **Python 3.11** - Programming language
- **discord.py** - Discord bot library
- **requests** - HTTP library for Twitter API calls
- **Flask** - Web server for embed pages
- **python-dotenv** - Environment variable management

---

## ✨ Latest Updates - 2025-11-29

✅ Instant tweet fetching on startup (with retry logic)  
✅ FixTweet-style embed formatting  
✅ Videos embedded inside tweet cards  
✅ Smart rate-limit handling  
✅ Top 2 tweets fetched instead of 5  
✅ Dual bot instance setup complete  
✅ Independent duplicate prevention  

---

## 📝 Workflows Running

1. **Embed Server** - Flask web server (port 5000) - generates tweet embeds
2. **Twitter Discord Bot** - Main bot monitoring @NFL
3. **Twitter Discord Bot 2** - Secondary bot monitoring @arkdesignss (currently disabled)
