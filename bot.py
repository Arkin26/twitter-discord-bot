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
        """Fetch tweets with optimized ZenRows configuration"""
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
            
            print(f"📤 Requesting via ZenRows...")
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                
                # OPTIMAL ZenRows parameters for Twitter based on 2024 best practices
                response = self.zenrows_client.get(
                    url,
                    headers=headers,
                    params={
                        # Core rendering
                        "js_render": "true",           # MANDATORY for Twitter (5 credits)
                        "premium_proxy": "true",       # Essential for anti-bot bypass (10-25 credits)
                        "proxy_country": "us",         # Match geo-location expectations
                        
                        # Advanced rendering
                        "json_response": "true",       # Captures XHR/Fetch requests
                        "original_status": "true",     # Get original HTTP status
                        
                        # Performance tuning
                        "window_width": "1920",        # Standard browser size
                        "window_height": "1080",       # Standard browser size
                        "block_resources": "image",    # Block images to speed up rendering
                    }
                )
                
                html = response.text
                print(f"📄 ZenRows received {len(html)} bytes")
                
                if len(html) > 2000:  # Minimum for valid Twitter page
                    tweets = self.parse_tweets(html)
                    if tweets:
                        print(f"✅ Found {len(tweets)} tweets")
                        self.save_last_tweet_id(tweets[0]["id"])
                        return tweets
                    else:
                        print(f"⚠️ HTML received but no tweets parsed. HTML length: {len(html)}")
                else:
                    print(f"⚠️ HTML too small ({len(html)} bytes). JS rendering may not be working.")
                        
            except Exception as ze:
                print(f"⚠️ ZenRows error: {ze}")
                import traceback
                traceback.print_exc()
            
            return []

        except Exception as e:
            print(f"❌ Error fetching tweets: {e}")
            return []

    def parse_tweets(self, html):
        """Parse tweets from HTML content with multiple fallback strategies"""
        tweets = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Method 1: Look for article tags with data-testid
            articles = soup.find_all('article', attrs={'data-testid': 'tweet'})
            print(f"🔍 Found {len(articles)} article[data-testid=tweet]")
            
            # Method 2: Just find all article tags
            if not articles:
                articles = soup.find_all('article')
                print(f"🔍 Found {len(articles)} plain article tags")
            
            # Method 3: Find divs with role=article
            if not articles:
                articles = soup.find_all('div', attrs={'role': 'article'})
                print(f"🔍 Found {len(articles)} div[role=article]")
            
            # Extract tweets from articles
            if articles:
                seen_ids = set()
                for article in articles[:10]:
                    # Look for status link in article
                    link = article.find('a', href=re.compile(r'/status/\d+'))
                    if not link:
                        continue
                    
                    href = link.get('href', '')
                    match = re.search(r'/status/(\d+)', href)
                    if not match:
                        continue
                    
                    tweet_id = match.group(1)
                    if tweet_id in seen_ids or (self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id)):
                        continue
                    seen_ids.add(tweet_id)
                    
                    # Extract tweet text from article
                    text_div = article.find('div', attrs={'data-testid': 'tweetText'})
                    if not text_div:
                        text_div = article.find('div', attrs={'lang': True})
                    
                    text = ""
                    if text_div:
                        text = text_div.get_text(strip=True)[:280]
                    else:
                        # Fallback: get all text but filter out UI elements
                        full_text = article.get_text(strip=True, separator=' ')
                        # Keep only first 280 chars that look like tweet content
                        text = full_text[:500]
                    
                    if text and len(text) > 5:
                        tweets.append({
                            'id': tweet_id,
                            'content': text,
                            'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                            'media_url': None
                        })
            
            # Fallback: Search for tweet URLs anywhere in HTML
            if not tweets:
                print("🔎 Fallback: Searching for tweet URLs in HTML...")
                for link in soup.find_all('a', href=re.compile(r'/status/\d+')):
                    href = link.get('href', '')
                    match = re.search(r'/status/(\d+)', href)
                    if not match:
                        continue
                    
                    tweet_id = match.group(1)
                    if self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id):
                        continue
                    
                    tweets.append({
                        'id': tweet_id,
                        'content': f"Tweet from @{TWITTER_USERNAME}",
                        'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                        'media_url': None
                    })
                    if len(tweets) >= 5:
                        break
            
            print(f"💾 Extracted {len(tweets)} tweets total")
            return list(reversed(tweets))[:10]
        
        except Exception as e:
            print(f"❌ Error parsing tweets: {e}")
            import traceback
            traceback.print_exc()
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
