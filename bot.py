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

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "NFL")
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

LAST_TWEET_FILE = "last_tweet.json"


class TwitterDiscordBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        
        self.channel = None
        self.last_tweet_id = self.load_last_tweet_id()
        self.client = ZenRowsClient(ZENROWS_API_KEY) if ZENROWS_API_KEY else None

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
        if not self.client:
            print("❌ ZenRows client not initialized")
            return []

        try:
            url = f"https://twitter.com/{TWITTER_USERNAME}"
            
            print(f"🌐 Fetching {url} via ZenRows...")
            response = self.client.get(url, params={
                "js_render": "true",
                "premium_proxy": "true"
            })
            
            html = response.text
            print(f"📄 Received {len(html)} bytes of HTML")
            
            tweets = self.parse_tweets_from_html(html)
            print(f"✅ Parsed {len(tweets)} tweets from HTML")
            
            if tweets:
                self.save_last_tweet_id(tweets[0]["id"])
            
            return tweets

        except Exception as e:
            print(f"❌ Error fetching tweets: {e}")
            return []

    def parse_tweets_from_html(self, html):
        """Parse tweets from Twitter HTML using BeautifulSoup"""
        tweets = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all tweet containers
            tweet_containers = soup.find_all('article', attrs={'data-testid': 'tweet'})
            
            print(f"🔍 Found {len(tweet_containers)} tweet containers")
            
            for container in tweet_containers[:10]:  # Get top 10
                try:
                    # Extract tweet ID
                    tweet_link = container.find('a', href=re.compile(r'/\w+/status/\d+'))
                    if not tweet_link:
                        continue
                    
                    # Get tweet ID from URL
                    match = re.search(r'/status/(\d+)', tweet_link['href'])
                    if not match:
                        continue
                    
                    tweet_id = match.group(1)
                    
                    # Skip if we've seen this tweet before
                    if self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id):
                        continue
                    
                    # Extract tweet text
                    text_elem = container.find('div', {'data-testid': 'tweetText'})
                    text = text_elem.get_text(strip=True) if text_elem else ""
                    
                    if not text:
                        continue
                    
                    # Extract media URL if present
                    media_url = None
                    img = container.find('img', {'alt': re.compile(r'Image')})
                    if img:
                        media_url = img.get('src')
                    
                    # Look for video in iframe or video tags
                    if not media_url:
                        video = container.find('video')
                        if video:
                            source = video.find('source')
                            if source:
                                media_url = source.get('src')
                    
                    tweets.append({
                        'id': tweet_id,
                        'content': text,
                        'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                        'media_url': media_url
                    })
                    
                except Exception as e:
                    print(f"⚠️ Error parsing individual tweet: {e}")
                    continue
            
            return list(reversed(tweets))  # Reverse to get oldest first
            
        except Exception as e:
            print(f"❌ Error parsing HTML: {e}")
            return []

    async def post_tweet_to_discord(self, tweet):
        try:
            embed = discord.Embed(
                description=tweet.get("content", ""),
                color=0x1DA1F2,
                timestamp=datetime.now(),
                url=tweet.get("url", "")
            )

            embed.set_author(
                name=f"@{TWITTER_USERNAME}",
                url=f"https://twitter.com/{TWITTER_USERNAME}",
            )

            embed.set_footer(text="Twitter")

            content = tweet.get("media_url") or None

            await self.channel.send(content=content, embed=embed)
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
    print("🚀 Starting Twitter to Discord bot (ZenRows)...")
    
    if not validate_config():
        exit(1)
    
    bot = TwitterDiscordBot()
    bot.run(DISCORD_BOT_TOKEN)
