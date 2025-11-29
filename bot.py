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
EMBED_SERVER_URL = os.getenv('REPLIT_DOMAINS', '').split(',')[0].strip() if os.getenv('REPLIT_DOMAINS') else 'localhost:5000'
if EMBED_SERVER_URL:
    EMBED_SERVER_URL = f"https://{EMBED_SERVER_URL.strip()}" if "://" not in EMBED_SERVER_URL else EMBED_SERVER_URL

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
    """Fetch tweets from Twitter API v2 with media"""
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
        
        # Get tweets with media
        tweets_url = f'https://api.twitter.com/2/users/{user_id}/tweets'
        params = {
            'max_results': 2,
            'tweet.fields': 'created_at,public_metrics',
            'expansions': 'attachments.media_keys,author_id',
            'media.fields': 'media_key,type,url,preview_image_url,variants,public_metrics'
        }
        
        tweets_response = requests.get(tweets_url, headers=headers, params=params, timeout=10)
        
        if tweets_response.status_code != 200:
            print(f"❌ Tweets lookup failed: {tweets_response.status_code}")
            return []
        
        response_data = tweets_response.json()
        tweets = []
        media_dict = {}
        
        # Build media lookup
        if 'includes' in response_data and 'media' in response_data['includes']:
            for media in response_data['includes']['media']:
                media_dict[media['media_key']] = media
        
        if 'data' in response_data:
            for tweet in response_data['data']:
                media_list = []
                
                # Extract media from tweet
                if 'attachments' in tweet and 'media_keys' in tweet['attachments']:
                    for media_key in tweet['attachments']['media_keys']:
                        if media_key in media_dict:
                            media = media_dict[media_key]
                            video_url = None
                            
                            # Extract video URL from variants if available
                            if media.get('type') in ['video', 'animated_gif'] and 'variants' in media:
                                for variant in media['variants']:
                                    if variant.get('content_type') == 'video/mp4':
                                        video_url = variant.get('url')
                                        break
                            
                            media_list.append({
                                'type': media.get('type'),
                                'url': media.get('url'),
                                'preview_image_url': media.get('preview_image_url'),
                                'video_url': video_url
                            })
                
                tweets.append({
                    'id': tweet['id'],
                    'text': tweet['text'],
                    'url': f'https://x.com/{username}/status/{tweet["id"]}',
                    'created_at': tweet.get('created_at', ''),
                    'metrics': tweet.get('public_metrics', {}),
                    'media': media_list
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
        # Post top 2 tweets immediately
        await tweet_checker()
        print('📢 Posted initial tweets')
        # Then start the loop
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
    
    for tweet in tweets:
        if tweet['id'] in posted:
            continue
        
        try:
            # Extract media
            image_url = None
            if tweet['media']:
                for media in tweet['media']:
                    if media['type'] == 'photo' and media.get('url'):
                        image_url = media['url']
                        break
                    elif media['type'] in ['video', 'animated_gif']:
                        if media.get('preview_image_url'):
                            image_url = media['preview_image_url']
                        break
            
            # Create fixtweet-style embed
            embed = discord.Embed(
                description=tweet['text'],
                url=tweet['url'],
                color=0x1F51BA
            )
            embed.set_author(name="@NFL", url=tweet['url'])
            
            # Add metrics inline
            likes = tweet['metrics'].get('like_count', 0)
            retweets = tweet['metrics'].get('retweet_count', 0)
            replies = tweet['metrics'].get('reply_count', 0)
            views = tweet['metrics'].get('impression_count', 0)
            metrics_line = f"💬 {replies}  🔄 {retweets}  ❤️ {likes}  👁️ {views}"
            embed.add_field(name=metrics_line, value="", inline=False)
            
            # Add image/video inside embed
            if image_url:
                embed.set_image(url=image_url)
            
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
