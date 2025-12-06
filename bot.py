import discord
from discord.ext import commands, tasks
import os
import json
import requests
import re
from dotenv import load_dotenv
import feedparser

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Track posted tweets to avoid duplicates
POSTED_FILE = "posted_tweets.json"

def load_posted():
    """Load list of already posted tweet IDs"""
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_posted(tweet_ids):
    """Save posted tweet IDs (keep last 100)"""
    with open(POSTED_FILE, 'w') as f:
        json.dump(tweet_ids[-100:], f, indent=2)

# Load posted tweets on startup
posted_tweets = load_posted()

def get_nfl_tweets_from_rss():
    """Fetch latest NFL tweets using RSS feed via Nitter"""
    try:
        # Using nitter.poast.org RSS feed (public Nitter instance)
        rss_url = "https://nitter.poast.org/NFL/rss"
        
        feed = feedparser.parse(rss_url)
        
        tweets = []
        for entry in feed.entries[:10]:  # Get last 10 tweets
            # Extract tweet ID from link
            link = entry.link
            match = re.search(r'/status/(\d+)', link)
            if match:
                tweet_id = match.group(1)
                tweets.append({
                    'id': tweet_id,
                    'text': entry.title,
                    'link': link
                })
        
        return tweets
    except Exception as e:
        print(f"❌ RSS fetch error: {e}")
        return []

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as: {bot.user}")
    print(f"📺 Monitoring channel ID: {DISCORD_CHANNEL_ID}")
    print(f"📝 Already posted {len(posted_tweets)} tweets")
    
    # Start the auto-posting loop
    tweet_loop.start()

@tasks.loop(minutes=2)
async def tweet_loop():
    """Check for new NFL tweets every 2 minutes"""
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    
    if not channel:
        print("❌ Channel not found!")
        return
    
    try:
        print("🔍 Checking for new NFL tweets...")
        
        # Get tweets from RSS
        tweets = get_nfl_tweets_from_rss()
        
        if not tweets:
            print("⚠️ No tweets found from RSS")
            return
        
        print(f"📊 Found {len(tweets)} total tweets")
        
        # Check for new tweets
        new_count = 0
        for tweet in tweets:
            tweet_id = tweet['id']
            
            # Skip if already posted
            if tweet_id in posted_tweets:
                continue
            
            # Build FxTwitter link - Discord will auto-embed with video!
            fxtwitter_url = f"https://fxtwitter.com/NFL/status/{tweet_id}"
            
            # Send to Discord
            await channel.send(fxtwitter_url)
            
            # Track it
            posted_tweets.append(tweet_id)
            new_count += 1
            
            print(f"✅ Posted tweet: {tweet_id}")
        
        # Save to file
        if new_count > 0:
            save_posted(posted_tweets)
            print(f"📊 Posted {new_count} new tweet(s)")
        else:
            print("✓ No new tweets")
            
    except Exception as e:
        print(f"❌ Error in tweet loop: {e}")

@bot.command()
async def tweet(ctx, url: str):
    """
    Manually post any tweet with working video embed
    Usage: !tweet https://twitter.com/user/status/123456
    """
    try:
        # Extract tweet ID and username from URL first
        match = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)", url)
        
        if not match:
            return await ctx.send("❌ Invalid tweet URL. Use: `!tweet https://twitter.com/user/status/123`", delete_after=5)
        
        username = match.group(1)
        tweet_id = match.group(2)
        
        # Build FxTwitter link
        fxtwitter_url = f"https://fxtwitter.com/{username}/status/{tweet_id}"
        
        # Try to delete the user's command message to avoid duplicate embeds
        try:
            await ctx.message.delete()
        except discord.errors.Forbidden:
            print("⚠️ Bot lacks 'Manage Messages' permission")
        except Exception as e:
            print(f"⚠️ Could not delete message: {e}")
        
        # Send the FxTwitter link - Discord handles the rest!
        await ctx.send(fxtwitter_url)
        
        print(f"✅ Manual tweet posted: {tweet_id}")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}", delete_after=5)
        print(f"❌ Command error: {e}")

@bot.command()
async def status(ctx):
    """Check bot status"""
    await ctx.send(
        f"✅ **Bot Status**\n"
        f"📺 Channel: <#{DISCORD_CHANNEL_ID}>\n"
        f"📝 Tracked tweets: {len(posted_tweets)}\n"
        f"🔄 Loop running: {tweet_loop.is_running()}"
    )

@bot.command()
async def clear(ctx):
    """Clear posted tweets history (admin only)"""
    global posted_tweets
    posted_tweets = []
    save_posted(posted_tweets)
    await ctx.send("✅ Cleared posted tweets history!")

# Run the bot
bot.run(DISCORD_TOKEN)
