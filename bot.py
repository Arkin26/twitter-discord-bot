import discord
from discord.ext import tasks
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import re
import time

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "nikhilraj__")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

LAST_TWEET_FILE = "last_tweet.json"


class TwitterDiscordBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        
        self.channel = None
        self.last_tweet_id = self.load_last_tweet_id()
        self.session = requests.Session()
        self.setup_session()

    def setup_session(self):
        """Setup session with proper headers to bypass basic anti-bot measures"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)

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
        print(f"🔑 Using FREE web scraping (no API needed)")
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
        """Fetch tweets using free web scraping - NO API KEY NEEDED"""
        try:
            print(f"🌐 Fetching tweets from @{TWITTER_USERNAME}...")
            
            # Multiple URLs to try
            urls = [
                f"https://twitter.com/{TWITTER_USERNAME}",
                f"https://nitter.net/{TWITTER_USERNAME}",  # Nitter mirror (lightweight)
            ]
            
            tweets = []
            
            for url in urls:
                try:
                    print(f"📤 Trying: {url}")
                    
                    # Add retry logic
                    for attempt in range(3):
                        try:
                            response = self.session.get(url, timeout=15)
                            
                            if response.status_code == 200:
                                print(f"✅ Got response ({len(response.text)} bytes)")
                                tweets = self.parse_tweets(response.text)
                                
                                if tweets:
                                    print(f"✅ Found {len(tweets)} tweets from {url}")
                                    self.save_last_tweet_id(tweets[0]["id"])
                                    return tweets
                                else:
                                    print(f"⏭️ No tweets found at {url}, trying next source...")
                                break
                            elif response.status_code == 429:
                                wait_time = 2 ** attempt
                                print(f"⚠️ Rate limited. Waiting {wait_time}s before retry...")
                                await asyncio.sleep(wait_time)
                            else:
                                print(f"⚠️ Status {response.status_code}")
                                break
                                
                        except Exception as e:
                            wait_time = 2 ** attempt
                            print(f"⚠️ Attempt {attempt + 1} failed: {str(e)[:50]}")
                            if attempt < 2:
                                await asyncio.sleep(wait_time)
                    
                except Exception as url_err:
                    print(f"⚠️ Error with {url}: {str(url_err)[:50]}")
                    continue
            
            return tweets

        except Exception as e:
            print(f"❌ Error: {e}")
            return []

    def parse_tweets(self, html):
        """Parse tweets from HTML"""
        tweets = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Strategy 1: Look for tweets with status URLs
            tweet_links = soup.find_all('a', href=re.compile(r'/\w+/status/\d+'))
            print(f"🔍 Found {len(tweet_links)} tweet links")
            
            seen_ids = set()
            
            for link in tweet_links[:20]:
                try:
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
                    
                    # Get parent article/div for text content
                    parent = link.find_parent(['article', 'div', 'main'])
                    text = ""
                    
                    if parent:
                        # Try to find tweet text div
                        text_div = parent.find('div', attrs={'data-testid': 'tweetText'})
                        if text_div:
                            text = text_div.get_text(strip=True)[:280]
                        else:
                            # Fallback: get all text from parent
                            text = parent.get_text(strip=True)[:500]
                    
                    # Clean up text - remove extra whitespace
                    text = ' '.join(text.split())
                    
                    if not text or len(text) < 5:
                        text = f"New tweet from @{TWITTER_USERNAME}"
                    
                    tweets.append({
                        'id': tweet_id,
                        'content': text,
                        'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                    })
                    
                except Exception as e:
                    continue
            
            # Strategy 2: If no tweets found, try to extract from any tweet-like content
            if not tweets:
                print("🔎 Using fallback extraction method...")
                # Look for any div with nested tweet-like structure
                for elem in soup.find_all(['article', 'div'], limit=50):
                    text = elem.get_text(strip=True)
                    # Check if element has tweet-like characteristics
                    if len(text) > 20 and len(text) < 300:
                        # Try to find tweet ID in nearby links
                        links = elem.find_all('a', href=re.compile(r'/status/\d+'))
                        if links:
                            for l in links:
                                match = re.search(r'/status/(\d+)', l.get('href', ''))
                                if match:
                                    tweet_id = match.group(1)
                                    if self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id):
                                        continue
                                    
                                    tweets.append({
                                        'id': tweet_id,
                                        'content': text,
                                        'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                                    })
                                    break
                            if len(tweets) >= 5:
                                break
            
            print(f"💾 Extracted {len(tweets)} tweets")
            return list(reversed(tweets))[:10]
        
        except Exception as e:
            print(f"❌ Parse error: {e}")
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
            print(f"❌ Error posting: {e}")


def validate_config():
    errors = []
    
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN is required")
    if not DISCORD_CHANNEL_ID:
        errors.append("DISCORD_CHANNEL_ID is required")
    if not TWITTER_USERNAME:
        errors.append("TWITTER_USERNAME is required")
    
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


if __name__ == "__main__":
    print("🚀 Starting Twitter to Discord bot (FREE method)...")
    
    if not validate_config():
        exit(1)
    
    bot = TwitterDiscordBot()
    bot.run(DISCORD_BOT_TOKEN)
