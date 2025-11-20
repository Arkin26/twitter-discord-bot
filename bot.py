import discord
from discord.ext import tasks
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from zenrows import ZenRowsClient
from bs4 import BeautifulSoup
import re
import time
import requests

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "nikhilraj__")
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

LAST_TWEET_FILE = "last_tweet.json"


class TwitterDiscordBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        
        self.channel = None
        self.last_tweet_id = self.load_last_tweet_id()
        self.zenrows_client = ZenRowsClient(ZENROWS_API_KEY) if ZENROWS_API_KEY else None
        self.last_fetch_time = 0

    def load_last_tweet_id(self):
        if os.path.exists(LAST_TWEET_FILE):
            try:
                with open(LAST_TWEET_FILE, "r") as f:
                    return json.load(f).get("last_tweet_id")
            except Exception as e:
                print(f"⚠️ Error loading last tweet: {e}")
        return None

    def save_last_tweet_id(self, tweet_id):
        try:
            with open(LAST_TWEET_FILE, "w") as f:
                json.dump({"last_tweet_id": tweet_id}, f)
            self.last_tweet_id = tweet_id
        except Exception as e:
            print(f"⚠️ Error saving last tweet: {e}")

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

        if not DISCORD_CHANNEL_ID:
            print("❌ DISCORD_CHANNEL_ID not set")
            await self.close()
            return

        self.channel = self.get_channel(int(DISCORD_CHANNEL_ID))
        if not self.channel:
            print(f"❌ Channel {DISCORD_CHANNEL_ID} not found")
            await self.close()
            return

        print(f"📡 Monitoring Twitter @{TWITTER_USERNAME}")
        print(f"🔑 Using ZenRows API")
        print(f"⏱️ Poll interval: {POLL_INTERVAL_SECONDS}s")

        self.check_tweets.start()

    @tasks.loop(seconds=POLL_INTERVAL_SECONDS)
    async def check_tweets(self):
        print("🔍 Checking for new tweets…")

        tweets = await self.get_new_tweets()
        if not tweets:
            print("📭 No new tweets")
            return

        print(f"📬 Found {len(tweets)} new tweet(s)")
        for tweet in tweets:
            await self.post_tweet_to_discord(tweet)
            await asyncio.sleep(1)

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.wait_until_ready()

    async def get_new_tweets(self):
        """Fetch tweets with fallback methods"""
        # Rate limit - wait at least 5 seconds between requests
        now = time.time()
        if now - self.last_fetch_time < 5:
            await asyncio.sleep(5 - (now - self.last_fetch_time))
        self.last_fetch_time = time.time()

        if not self.zenrows_client:
            print("❌ ZenRows client not initialized")
            return []

        try:
            print(f"🌐 Fetching tweets from @{TWITTER_USERNAME}...")
            url = f"https://twitter.com/{TWITTER_USERNAME}"
            
            # Try ZenRows with aggressive parameters
            print(f"📤 Requesting via ZenRows...")
            try:
                response = self.zenrows_client.get(url, params={
                    "js_render": "true",
                    "premium_proxy": "true",
                    "wait_for": "article",  # Wait for article elements to load
                    "render_js": "true",
                    "auto_parse": "false"
                })
                
                html = response.text
                print(f"📄 Received {len(html)} bytes")
                
                tweets = self.parse_tweets(html)
                if tweets:
                    print(f"✅ Found {len(tweets)} tweets")
                    self.save_last_tweet_id(tweets[0]["id"])
                    return tweets
            except Exception as ze:
                print(f"⚠️ ZenRows error: {ze}")
            
            # Fallback: Try regular requests with browser headers
            print("🔄 Trying fallback method with browser headers...")
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                }
                
                session = requests.Session()
                resp = session.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                
                print(f"📄 Fallback received {len(resp.text)} bytes")
                tweets = self.parse_tweets(resp.text)
                
                if tweets:
                    print(f"✅ Found {len(tweets)} tweets via fallback")
                    self.save_last_tweet_id(tweets[0]["id"])
                    return tweets
            except Exception as fe:
                print(f"⚠️ Fallback error: {fe}")
            
            return []

        except Exception as e:
            print(f"❌ Error fetching tweets: {e}")
            return []

    def parse_tweets(self, html):
        """Parse tweets from HTML content"""
        tweets = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Method 1: Look for tweet links
            tweet_links = soup.find_all('a', href=re.compile(r'/\w+/status/\d+'))
            print(f"🔍 Found {len(tweet_links)} tweet links")
            
            if tweet_links:
                seen_ids = set()
                for link in tweet_links[:20]:
                    href = link.get('href', '')
                    match = re.search(r'/status/(\d+)', href)
                    if not match:
                        continue
                    
                    tweet_id = match.group(1)
                    if tweet_id in seen_ids:
                        continue
                    seen_ids.add(tweet_id)
                    
                    if self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id):
                        continue
                    
                    # Get text from parent container
                    parent = link.find_parent(['article', 'div'])
                    text = ""
                    if parent:
                        text = parent.get_text(strip=True, separator=' ')[:280]
                    
                    if not text or len(text) < 5:
                        text = f"Tweet from @{TWITTER_USERNAME}"
                    
                    tweets.append({
                        'id': tweet_id,
                        'content': text,
                        'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                        'media_url': None
                    })
            
            # Method 2: Search for tweet IDs in page text as backup
            if not tweets:
                print("🔎 Searching for tweet IDs in page content...")
                all_text = soup.get_text()
                tweet_ids = re.findall(r'(?:status|/|:)(\d{16,20})', all_text)
                
                if tweet_ids:
                    print(f"📍 Found {len(set(tweet_ids))} potential tweet IDs")
                    for tweet_id in list(set(tweet_ids))[:5]:
                        if self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id):
                            continue
                        
                        tweets.append({
                            'id': tweet_id,
                            'content': f"New tweet from @{TWITTER_USERNAME}",
                            'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                            'media_url': None
                        })
            
            return list(reversed(tweets))[:10]
        
        except Exception as e:
            print(f"❌ Error parsing tweets: {e}")
            return []

    async def post_tweet_to_discord(self, tweet):
        try:
            embed = discord.Embed(
                description=tweet.get("content", "")[:2000],
                color=0x1DA1F2,
                timestamp=datetime.now(),
                url=tweet.get("url", "")
            )

            embed.set_author(
                name=f"@{TWITTER_USERNAME}",
                url=f"https://twitter.com/{TWITTER_USERNAME}",
            )

            embed.set_footer(text="Twitter")

            await self.channel.send(embed=embed)
            print(f"✅ Posted tweet {tweet['id']} to Discord")

        except Exception as e:
            print(f"❌ Error posting tweet: {e}")


def validate_config():
    errors = []
    
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN is required")
    if not DISCORD_CHANNEL_ID:
        errors.append("DISCORD_CHANNEL_ID is required")
    if not ZENROWS_API_KEY:
        errors.append("ZENROWS_API_KEY is required")
    
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


if __name__ == "__main__":
    print("🚀 Starting Twitter to Discord bot...")
    
    if not validate_config():
        exit(1)
    
    bot = TwitterDiscordBot()
    bot.run(DISCORD_BOT_TOKEN)
