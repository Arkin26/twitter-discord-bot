import discord
from discord.ext import commands, tasks
import os
import requests
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Track posted tweets to avoid duplicates
POSTED_TWEETS_FILE = 'posted_tweets.json'

def load_posted_tweets():
    if Path(POSTED_TWEETS_FILE).exists():
        try:
            return json.load(open(POSTED_TWEETS_FILE))
        except:
            return {}
    return {}

def save_posted_tweets(data):
    json.dump(data, open(POSTED_TWEETS_FILE, 'w'), indent=2)

def get_tweets(username):
    """Fetch tweets from Twitter API v2"""
    if not TWITTER_BEARER_TOKEN:
        return []
    
    try:
        headers = {'Authorization': f'Bearer {TWITTER_BEARER_TOKEN}'}
        
        # Get user ID
        user_url = f'https://api.twitter.com/2/users/by/username/{username}'
        user_response = requests.get(user_url, headers=headers, timeout=10)
        
        if user_response.status_code != 200:
            print(f"❌ User lookup failed: {user_response.status_code}")
            return []
        
        user_id = user_response.json()['data']['id']
        
        # Get tweets
        tweets_url = f'https://api.twitter.com/2/users/{user_id}/tweets'
        params = {
            'max_results': 20,
            'tweet.fields': 'created_at,public_metrics',
            'expansions': 'author_id'
        }
        
        tweets_response = requests.get(tweets_url, headers=headers, params=params, timeout=10)
        
        if tweets_response.status_code != 200:
            print(f"❌ Tweets lookup failed: {tweets_response.status_code}")
            return []
        
        data = tweets_response.json()
        tweets = []
        
        if 'data' in data:
            for tweet in data['data']:
                tweets.append({
                    'id': tweet['id'],
                    'text': tweet['text'],
                    'url': f'https://x.com/{username}/status/{tweet["id"]}',
                    'created_at': tweet.get('created_at', ''),
                    'metrics': tweet.get('public_metrics', {})
                })
        
        return tweets
    except Exception as e:
        print(f"❌ Error fetching tweets: {e}")
        return []

@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    print(f'📢 Target channel: {DISCORD_CHANNEL_ID}')
    
    if not tweet_checker.is_running():
        tweet_checker.start()
        print('🔄 Tweet checker started')

@tasks.loop(minutes=5)
async def tweet_checker():
    """Check for new tweets every 5 minutes"""
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        return
    
    posted = load_posted_tweets()
    tweets = get_tweets('NFL')
    
    if not tweets:
        print("ℹ️  No tweets found")
        return
    
    for tweet in reversed(tweets):
        if tweet['id'] in posted:
            continue
        
        try:
            # Create embed with link
            embed = discord.Embed(
                title="Tweet from @NFL",
                description=tweet['text'][:2000],
                url=tweet['url'],
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Link", value=tweet['url'], inline=False)
            if tweet['metrics']:
                embed.add_field(name="❤️ Likes", value=str(tweet['metrics'].get('like_count', 0)), inline=True)
                embed.add_field(name="🔄 Retweets", value=str(tweet['metrics'].get('retweet_count', 0)), inline=True)
            embed.set_footer(text="X.com")
            
            await channel.send(embed=embed)
            print(f"✅ Posted tweet {tweet['id']}")
            
            posted[tweet['id']] = True
            save_posted_tweets(posted)
        except Exception as e:
            print(f"❌ Error posting: {e}")

@tweet_checker.before_loop
async def before_tweet_checker():
    await bot.wait_until_ready()

@bot.command()
async def check(ctx):
    """Manually check for new tweets"""
    await ctx.send("🔍 Checking for new tweets...")
    tweets = get_tweets('NFL')
    if tweets:
        await ctx.send(f"✅ Found {len(tweets)} tweets")
    else:
        await ctx.send("❌ No tweets found")

if __name__ == '__main__':
    if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID or not TWITTER_BEARER_TOKEN:
        print('❌ Missing DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, or TWITTER_BEARER_TOKEN')
        exit(1)
    print('🚀 Starting Twitter to Discord Bot...')
    bot.run(DISCORD_TOKEN)
