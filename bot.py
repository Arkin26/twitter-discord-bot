import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))
FOLLOWED_FILE = 'followed.json'

def load_followed():
    if Path(FOLLOWED_FILE).exists():
        try:
            return json.load(open(FOLLOWED_FILE))
        except:
            return {}
    return {}

def save_followed(data):
    json.dump(data, open(FOLLOWED_FILE, 'w'), indent=2)

def scrape_tweets(username):
    """Scrape tweets using snscrape"""
    try:
        result = subprocess.run(
            ['python', 'fetch_tweets.py', username],
            capture_output=True,
            text=True,
            timeout=45
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except:
                print(f'JSON parse error: {result.stdout}')
                return []
        else:
            print(f'Scraper stderr: {result.stderr}')
            return []
    except Exception as e:
        print(f'Scrape exception: {e}')
        return []

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
followed = load_followed()

@bot.event
async def on_ready():
    print(f'✅ Bot logged in as {bot.user}')
    print(f'📢 Target channel: {DISCORD_CHANNEL_ID}')
    print(f'📌 Followed: {list(followed.keys())}')
    
    if not check_tweets.is_running():
        check_tweets.start()
        print('🔄 Tweet checker started')

@bot.event
async def on_message(message):
    if message.author.bot or not message.content.startswith('!'):
        return
    await bot.process_commands(message)

@bot.command()
async def follow(ctx, username: str):
    """Follow: !follow NFL"""
    username = username.lstrip('@')
    
    if username in followed:
        await ctx.send(f'Already following @{username}')
        return
    
    try:
        await ctx.send(f'🔍 Fetching tweets from @{username}...')
        tweets = await asyncio.to_thread(scrape_tweets, username)
        
        if not tweets or len(tweets) == 0:
            await ctx.send(f'❌ No tweets found for @{username}')
            return
        
        followed[username] = {
            'lastTweetId': str(tweets[0]['id']),
            'name': username
        }
        save_followed(followed)
        await ctx.send(f'✅ Following @{username} ({len(tweets)} tweets found)')
        print(f'✅ Now following @{username}')
    except Exception as e:
        await ctx.send(f'❌ Error: {str(e)[:80]}')
        print(f'❌ Follow error: {e}')

@bot.command()
async def unfollow(ctx, username: str):
    """Unfollow: !unfollow NFL"""
    username = username.lstrip('@')
    if username not in followed:
        await ctx.send(f'Not following @{username}')
        return
    del followed[username]
    save_followed(followed)
    await ctx.send(f'❌ Unfollowed @{username}')

@bot.command(name='list')
async def list_accounts(ctx):
    """List accounts: !list"""
    if not followed:
        await ctx.send('No accounts. Use `!follow <username>`')
        return
    await ctx.send('📋 Followed:\n' + '\n'.join([f'• @{u}' for u in followed.keys()]))

@tasks.loop(minutes=3)
async def check_tweets():
    """Check for new tweets every 3 minutes"""
    if not followed:
        return
    
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        return
    
    for username, data in list(followed.items()):
        try:
            print(f'🔍 Checking @{username}...')
            tweets = await asyncio.to_thread(scrape_tweets, username)
            
            if not tweets:
                print('  ℹ️ No tweets')
                continue
            
            last_id = data.get('lastTweetId')
            if last_id:
                new_tweets = [t for t in tweets if str(t['id']) > str(last_id)]
            else:
                new_tweets = [tweets[0]] if tweets else []
            
            if not new_tweets:
                print('  ✓ No new')
                continue
            
            for tweet in reversed(new_tweets):
                try:
                    embed = discord.Embed(
                        title=f"Tweet from @{username}",
                        description=tweet['text'][:2000],
                        url=tweet['url'],
                        color=discord.Color.blue(),
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text="X.com")
                    await channel.send(embed=embed)
                    print(f'  ✅ Posted {tweet["id"]}')
                except Exception as e:
                    print(f'  Error posting: {e}')
                await asyncio.sleep(0.5)
            
            followed[username]['lastTweetId'] = str(new_tweets[0]['id'])
            save_followed(followed)
            print(f'  💾 Updated')
        
        except Exception as e:
            print(f'❌ Error @{username}: {e}')
        
        await asyncio.sleep(1)

@check_tweets.before_loop
async def before_check_tweets():
    await bot.wait_until_ready()

if __name__ == '__main__':
    if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
        print('❌ Missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID')
        exit(1)
    print('🚀 Starting Discord Twitter bot with Twitter API v2...')
    bot.run(DISCORD_TOKEN)
