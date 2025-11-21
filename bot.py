import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# TwiKit for Twitter scraping
from twikit.guest import GuestClient
from twikit import TooManyRequests

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))

# State file
FOLLOWED_FILE = 'followed.json'

def load_followed():
    """Load followed accounts"""
    if Path(FOLLOWED_FILE).exists():
        try:
            with open(FOLLOWED_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_followed(data):
    """Save followed accounts"""
    with open(FOLLOWED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Initialize Discord bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# TwiKit guest client
guest_client = GuestClient()
followed = load_followed()

@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    print(f'📢 Target channel: {DISCORD_CHANNEL_ID}')
    print(f'📌 Followed accounts: {list(followed.keys())}')
    
    if not guest_client.is_activated:
        print('🔄 Initializing TwiKit guest client...')
        try:
            await guest_client.activate()
            print('✅ TwiKit guest client ready')
        except Exception as e:
            print(f'❌ TwiKit error: {e}')
    
    # Start the tweet checker
    if not check_tweets.is_running():
        check_tweets.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if not message.content.startswith('!'):
        return
    
    await bot.process_commands(message)

@bot.command()
async def follow(ctx, username: str):
    """Follow a Twitter account: !follow NFL"""
    username = username.lstrip('@').lower()
    
    if username in followed:
        await ctx.send(f'Already following @{username}')
        return
    
    try:
        # Verify user exists
        user = await guest_client.get_user_by_screen_name(username)
        print(f'✅ Fetched user @{username} (ID: {user.id})')
        
        # Get their recent tweets
        tweets = await guest_client.get_user_tweets(user.id)
        
        if tweets:
            last_tweet_id = tweets[0].id if tweets else None
            followed[username] = {
                'user_id': user.id,
                'lastTweetId': last_tweet_id,
                'name': user.name
            }
            save_followed(followed)
            tweet_count = len(tweets)
            await ctx.send(f'✅ Following @{username} (found {tweet_count} recent tweets)')
            print(f'✅ Now following @{username}')
        else:
            await ctx.send(f'❌ No tweets found for @{username}')
    
    except Exception as e:
        await ctx.send(f'❌ Error: User @{username} not found')
        print(f'❌ Error fetching @{username}: {e}')

@bot.command()
async def unfollow(ctx, username: str):
    """Unfollow a Twitter account: !unfollow NFL"""
    username = username.lstrip('@').lower()
    
    if username not in followed:
        await ctx.send(f'Not following @{username}')
        return
    
    del followed[username]
    save_followed(followed)
    await ctx.send(f'❌ Unfollowed @{username}')
    print(f'❌ Unfollowed @{username}')

@bot.command()
async def list(ctx):
    """List all followed accounts: !list"""
    if not followed:
        await ctx.send('No accounts being followed. Use `!follow <username>`')
        return
    
    usernames = '\n'.join([f'• @{u}' for u in followed.keys()])
    await ctx.send(f'📋 Followed accounts:\n{usernames}')

@tasks.loop(minutes=3)
async def check_tweets():
    """Check followed accounts for new tweets every 3 minutes"""
    if not followed:
        return
    
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print(f'❌ Channel {DISCORD_CHANNEL_ID} not found')
        return
    
    for username, data in list(followed.items()):
        try:
            print(f'🔍 Checking @{username}...')
            user_id = data.get('user_id')
            last_tweet_id = data.get('lastTweetId')
            
            if not user_id:
                print(f'⚠️ No user_id for @{username}')
                continue
            
            # Get recent tweets
            tweets = await guest_client.get_user_tweets(user_id)
            
            if not tweets:
                print(f'  ℹ️ No tweets found')
                continue
            
            # Find new tweets
            new_tweets = []
            for tweet in tweets:
                if last_tweet_id is None or int(tweet.id) > int(last_tweet_id):
                    new_tweets.append(tweet)
            
            if not new_tweets:
                print(f'  ✓ No new tweets')
                continue
            
            # Post new tweets (reverse order - oldest first)
            for tweet in reversed(new_tweets):
                try:
                    embed = discord.Embed(
                        title=f"New Tweet from @{username}",
                        description=tweet.text[:2000],  # Discord limit
                        url=f"https://x.com/{username}/status/{tweet.id}",
                        color=discord.Color.blue(),
                        timestamp=tweet.created_at if hasattr(tweet, 'created_at') else datetime.now()
                    )
                    embed.set_author(name=data.get('name', username), url=f"https://x.com/{username}")
                    embed.set_footer(text="Posted from X.com")
                    
                    await channel.send(embed=embed)
                    print(f'  ✅ Posted tweet {tweet.id}')
                    
                except Exception as e:
                    print(f'  ❌ Error posting tweet: {e}')
                
                await asyncio.sleep(0.5)  # Small delay between posts
            
            # Update last tweet ID
            if new_tweets:
                followed[username]['lastTweetId'] = new_tweets[0].id
                save_followed(followed)
                print(f'  💾 Updated last tweet ID')
        
        except TooManyRequests:
            print(f'⚠️ Rate limited for @{username}, will retry in 3 minutes')
        except Exception as e:
            print(f'❌ Error checking @{username}: {e}')
        
        await asyncio.sleep(1)  # Delay between accounts

@check_tweets.before_loop
async def before_check_tweets():
    """Wait for bot to be ready before starting the loop"""
    await bot.wait_until_ready()

# Error handling
@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f'❌ Error: {str(error)}')
    print(f'Command error: {error}')

# Run bot
if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print('❌ DISCORD_BOT_TOKEN not set in .env')
        exit(1)
    if not DISCORD_CHANNEL_ID or DISCORD_CHANNEL_ID == 0:
        print('❌ DISCORD_CHANNEL_ID not set in .env')
        exit(1)
    
    print('🚀 Starting Discord Twitter bot with TwiKit...')
    bot.run(DISCORD_TOKEN)
