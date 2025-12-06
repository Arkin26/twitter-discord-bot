import discord
from discord.ext import commands, tasks
import os
import json
import requests
import re
from dotenv import load_dotenv

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
        
        # Fetch latest tweets from NFL account
        url = "https://api.fxtwitter.com/NFL"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ FxTwitter API error: {response.status_code}")
            return
        
        data = response.json()
        tweets = data.get("tweets", [])
        
        if not tweets:
            print("⚠️ No tweets found")
            return
        
        # Check the latest 5 tweets for any new ones
        new_count = 0
        for tweet in tweets[:5]:
            tweet_id = tweet.get("id")
            
            # Skip if already posted
            if not tweet_id or tweet_id in posted_tweets:
                continue
            
            # Get username
            username = tweet.get("author", {}).get("screen_name", "NFL")
            
            # Build FxTwitter link - Discord will auto-embed with video!
            fxtwitter_url = f"https://fxtwitter.com/{username}/status/{tweet_id}"
            
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
        # Extract tweet ID and username from URL
        match = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)", url)
        
        if not match:
            return await ctx.send("❌ Invalid tweet URL. Use: `!tweet https://twitter.com/user/status/123`")
        
        username = match.group(1)
        tweet_id = match.group(2)
        
        # Build FxTwitter link
        fxtwitter_url = f"https://fxtwitter.com/{username}/status/{tweet_id}"
        
        # Send it - Discord handles the rest!
        await ctx.send(fxtwitter_url)
        
        print(f"✅ Manual tweet posted: {tweet_id}")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")
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
