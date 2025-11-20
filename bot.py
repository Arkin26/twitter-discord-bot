import discord
from discord.ext import tasks
import snscrape.modules.twitter as sntwitter
import os
from dotenv import load_dotenv
import json
from datetime import datetime
import asyncio

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
TWITTER_USERNAME = os.getenv('TWITTER_USERNAME', 'elonmusk')
POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '60'))

LAST_TWEET_FILE = 'last_tweet.json'

class TwitterDiscordBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.channel = None
        self.last_tweet_id = self.load_last_tweet_id()
        
    def load_last_tweet_id(self):
        try:
            if os.path.exists(LAST_TWEET_FILE):
                with open(LAST_TWEET_FILE, 'r') as f:
                    data = json.load(f)
                    tweet_id = data.get('last_tweet_id')
                    if tweet_id:
                        print(f'📝 Loaded last tweet ID: {tweet_id}')
                        return tweet_id
        except Exception as e:
            print(f'⚠️  Error loading last tweet ID: {e}')
        return None
    
    def save_last_tweet_id(self, tweet_id):
        try:
            with open(LAST_TWEET_FILE, 'w') as f:
                json.dump({'last_tweet_id': tweet_id}, f)
            self.last_tweet_id = tweet_id
        except Exception as e:
            print(f'⚠️  Error saving last tweet ID: {e}')
    
    async def on_ready(self):
        print(f'✅ Discord bot logged in as {self.user}')
        
        try:
            if not DISCORD_CHANNEL_ID:
                print('❌ DISCORD_CHANNEL_ID is not set')
                await self.close()
                return
                
            self.channel = self.get_channel(int(DISCORD_CHANNEL_ID))
            if not self.channel:
                print(f'❌ Could not find channel with ID: {DISCORD_CHANNEL_ID}')
                await self.close()
                return
            
            if not hasattr(self.channel, 'send'):
                print(f'❌ Channel {DISCORD_CHANNEL_ID} is not a text channel')
                await self.close()
                return
            
            channel_name = getattr(self.channel, 'name', 'Unknown')
            print(f'✅ Connected to Discord channel: {channel_name}')
            print(f'📊 Monitoring Twitter user: @{TWITTER_USERNAME}')
            print(f'⏱️  Poll interval: {POLL_INTERVAL_SECONDS} seconds')
            
            self.check_tweets.start()
        except Exception as e:
            print(f'❌ Error during setup: {e}')
            await self.close()
    
    @tasks.loop(seconds=POLL_INTERVAL_SECONDS)
    async def check_tweets(self):
        try:
            print('🔍 Checking for new tweets...')
            tweets = await self.get_new_tweets()
            
            if tweets:
                print(f'📬 Found {len(tweets)} new tweet(s)')
                for tweet_data in tweets:
                    await self.post_tweet_to_discord(tweet_data)
                    await asyncio.sleep(1)
            else:
                print('📭 No new tweets')
                
        except Exception as e:
            print(f'⚠️  Error checking tweets: {e}')
    
    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.wait_until_ready()
    
    async def get_new_tweets(self):
        try:
            tweets = []
            scraper = sntwitter.TwitterUserScraper(TWITTER_USERNAME)
            
            for i, tweet in enumerate(scraper.get_items()):
                if i >= 10:
                    break
                
                if not hasattr(tweet, 'id') or not hasattr(tweet, 'content'):
                    continue
                
                if self.last_tweet_id and int(tweet.id) <= int(self.last_tweet_id):
                    break
                
                video_url = None
                if hasattr(tweet, 'media') and tweet.media:
                    for media in tweet.media:
                        if hasattr(media, 'variants') and media.variants:
                            mp4_variants = [v for v in media.variants if hasattr(v, 'contentType') and v.contentType == 'video/mp4']
                            if mp4_variants:
                                highest_quality = max(mp4_variants, key=lambda v: getattr(v, 'bitrate', 0) or 0)
                                video_url = highest_quality.url
                                break
                
                if not video_url and hasattr(tweet, 'content') and tweet.content:
                    for url in ['youtube.com', 'youtu.be', 'vimeo.com']:
                        if url in tweet.content:
                            links = tweet.content.split()
                            for link in links:
                                if url in link:
                                    video_url = link
                                    break
                            if video_url:
                                break
                
                tweets.append({
                    'id': tweet.id,
                    'url': getattr(tweet, 'url', ''),
                    'content': tweet.content or '',
                    'user': getattr(tweet, 'user', None),
                    'date': getattr(tweet, 'date', datetime.now()),
                    'video_url': video_url
                })
            
            if tweets:
                self.save_last_tweet_id(tweets[0]['id'])
            
            return list(reversed(tweets))
            
        except Exception as e:
            print(f'❌ Error fetching tweets: {e}')
            return []
    
    async def post_tweet_to_discord(self, tweet_data):
        try:
            if not self.channel or not hasattr(self.channel, 'send'):
                print('❌ Channel is not available')
                return
                
            embed = discord.Embed(
                description=tweet_data['content'],
                color=0x1DA1F2,
                timestamp=tweet_data['date'],
                url=tweet_data['url']
            )
            
            user = tweet_data.get('user')
            if user:
                displayname = getattr(user, 'displayname', 'Unknown')
                username = getattr(user, 'username', 'unknown')
                profile_image = getattr(user, 'profileImageUrl', '')
                
                embed.set_author(
                    name=f"{displayname} (@{username})",
                    icon_url=profile_image,
                    url=f"https://twitter.com/{username}"
                )
            
            embed.set_footer(text='Twitter')
            
            message_content = None
            if tweet_data.get('video_url'):
                print(f"📹 Tweet contains video: {tweet_data['video_url']}")
                message_content = tweet_data['video_url']
            
            await self.channel.send(content=message_content, embed=embed)
            print(f"✅ Posted tweet {tweet_data['id']} to Discord")
            
        except Exception as e:
            print(f'❌ Error posting tweet to Discord: {e}')

def validate_config():
    errors = []
    
    if not DISCORD_BOT_TOKEN:
        errors.append('DISCORD_BOT_TOKEN is required')
    if not DISCORD_CHANNEL_ID:
        errors.append('DISCORD_CHANNEL_ID is required')
    if not TWITTER_USERNAME:
        errors.append('TWITTER_USERNAME is required')
    
    if errors:
        print('❌ Configuration errors:')
        for error in errors:
            print(f'  - {error}')
        print('\n📝 Setup Instructions:')
        print('1. Copy .env.example to .env')
        print('2. Fill in your Discord bot token and channel ID')
        print('3. Set the Twitter username to monitor (no @ symbol)')
        print('\nNote: No Twitter API credentials needed - using free snscrape!')
        return False
    
    return True

if __name__ == '__main__':
    print('🚀 Starting Twitter to Discord bot (using snscrape)...')
    
    if not validate_config():
        exit(1)
    
    if not DISCORD_BOT_TOKEN:
        print('❌ DISCORD_BOT_TOKEN is required')
        exit(1)
    
    bot = TwitterDiscordBot()
    bot.run(DISCORD_BOT_TOKEN)
