# Twitter to Discord Bot (Free Version using snscrape)

A Python Discord bot that monitors a specific Twitter account and automatically posts new tweets to a designated Discord channel. The bot detects and embeds videos so they play directly in Discord.

**🎉 No Twitter API credentials needed - completely FREE!**

## Features

- **✅ Completely Free**: Uses snscrape library - no Twitter API costs
- **🎬 Video Embedding**: Automatically detects videos in tweets and embeds them in Discord
- **📊 Smart Tweet Tracking**: Remembers the last processed tweet to avoid duplicates
- **🔄 Auto-Refresh**: Checks for new tweets every 60 seconds (configurable)
- **💎 Rich Embeds**: Posts tweets with author information, timestamps, and proper formatting
- **⚙️ Easy Configuration**: Simple setup via environment variables

## How It Works

This bot uses **snscrape**, an open-source web scraping library, to monitor Twitter accounts without needing the expensive Twitter API ($200/month). It's completely free and works great for personal projects!

**Trade-offs compared to official API:**
- ✅ FREE (vs $200/month)
- ✅ No authentication needed
- ✅ No rate limits
- ⚠️ Slightly delayed (polls every 60 seconds instead of real-time streaming)
- ⚠️ Uses web scraping (may break if Twitter changes their website)

## Prerequisites

Before running this bot, you only need:

1. **Discord Bot Token**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application and add a bot
   - Copy the bot token
   - Invite the bot to your server with permissions: Send Messages, Embed Links

2. **Discord Channel ID**
   - Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
   - Right-click the channel where you want tweets posted
   - Click "Copy Channel ID"

3. **Twitter Username** to monitor (just the username, no @ symbol needed!)

**No Twitter API credentials needed!** 🎉

## Installation

1. The required Python packages are already installed:
   - discord.py
   - snscrape
   - python-dotenv

2. Create a `.env` file from the example:
```bash
cp .env.example .env
```

3. Edit `.env` and fill in your configuration:
```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=your_channel_id_here
TWITTER_USERNAME=elonmusk
POLL_INTERVAL_SECONDS=60
```

## Configuration

Edit the `.env` file with these variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DISCORD_BOT_TOKEN` | Your Discord bot token | Yes | - |
| `DISCORD_CHANNEL_ID` | The Discord channel ID where tweets will be posted | Yes | - |
| `TWITTER_USERNAME` | The Twitter username to monitor (without @) | Yes | elonmusk |
| `POLL_INTERVAL_SECONDS` | How often to check for new tweets (seconds) | No | 60 |

## Usage

Start the bot by clicking the **Run** button in Replit, or run:
```bash
python bot.py
```

The bot will:
1. Connect to Discord
2. Start monitoring the Twitter account via snscrape
3. Check for new tweets every 60 seconds
4. Post new tweets to your Discord channel with embedded videos

## How It Works

### Tweet Monitoring
- The bot uses snscrape to fetch tweets every 60 seconds (configurable)
- Fetches up to 10 recent tweets from the monitored account
- Only posts tweets that are newer than the last processed tweet
- Saves the last tweet ID to `last_tweet.json` to prevent duplicates

### Video Detection
The bot detects videos in two ways:
1. **Native Twitter Videos**: Extracts video URLs from tweet media
2. **External Video Links**: Detects YouTube, Vimeo, and other video platform links

### Discord Posting
- Creates rich embeds with author info, tweet text, and timestamp
- If a video is detected, includes the video URL for automatic embedding
- Discord will auto-embed Twitter videos and external video links

## Troubleshooting

### Bot doesn't post tweets
- Verify your Discord bot token is correct
- Check that the Twitter username is correct (no @ symbol)
- Ensure the bot has been invited to your Discord server
- Verify the Discord channel ID is correct
- Check the console logs for error messages

### Bot says "Cannot find channel"
- Make sure you've copied the correct channel ID
- Ensure the bot has been invited to your server
- Verify the bot has permission to view and send messages in that channel

### Videos not embedding
- Discord may not support all video formats
- External videos (YouTube, Vimeo) should embed automatically
- Twitter videos are posted as direct links for Discord to embed

### snscrape errors
- snscrape occasionally breaks when Twitter updates their website
- The library is actively maintained - wait for updates if this happens
- Consider using a paid alternative like TwitterAPI.io ($0.15/1K tweets) for production use

## File Structure

```
├── bot.py                # Main bot application
├── .env                  # Your configuration (not in git)
├── .env.example         # Example configuration
├── last_tweet.json      # Stores last processed tweet ID
├── requirements.txt     # Python dependencies (auto-managed)
└── README.md            # This file
```

## Advantages Over Twitter API

| Feature | This Bot (snscrape) | Twitter API Basic |
|---------|---------------------|-------------------|
| Cost | **FREE** | $200/month |
| Setup | No API application needed | Requires developer account approval |
| Rate Limits | None | 10,000 tweets/month |
| Authentication | None needed | API keys required |
| Best For | Personal projects, learning | Production apps |

## Upgrading to Paid Alternatives

If you need more reliability or real-time updates, consider these affordable alternatives:

- **TwitterAPI.io**: $0.15 per 1,000 tweets (~$2-3/month for typical use)
- **SociaVault**: 50 free credits to start, then pay-as-you-go

Both are 90%+ cheaper than the official Twitter API!

## License

MIT

## Credits

This bot uses:
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [snscrape](https://github.com/JustAnotherArchivist/snscrape) - Social media scraper
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
