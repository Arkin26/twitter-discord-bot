import discord
from discord.ext import tasks
import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
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
        self.driver = None

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

    def setup_driver(self):
        """Setup Selenium Chrome driver with headless mode"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✅ Selenium Chrome driver initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Chrome driver: {e}")
            self.driver = None

    def close_driver(self):
        """Close the Selenium driver"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass

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
        print(f"🔑 Using Selenium Browser Automation")
        print(f"⏱️ Poll interval: {POLL_INTERVAL_SECONDS}s")
        
        self.setup_driver()
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
        """Fetch tweets using Selenium browser automation"""
        if not self.driver:
            print("❌ Selenium driver not initialized")
            return []

        try:
            print(f"🌐 Loading Twitter profile for @{TWITTER_USERNAME}...")
            url = f"https://twitter.com/{TWITTER_USERNAME}"
            
            self.driver.get(url)
            
            # Wait for tweets to load (max 10 seconds)
            print("⏳ Waiting for tweets to load...")
            wait = WebDriverWait(self.driver, 10)
            
            try:
                # Wait for article elements (tweets)
                wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "article")))
            except:
                print("⚠️ Timeout waiting for tweets")
            
            # Extract tweets
            tweets = []
            articles = self.driver.find_elements(By.TAG_NAME, "article")
            print(f"🔍 Found {len(articles)} article elements")
            
            for article in articles[:10]:
                try:
                    # Get tweet link
                    links = article.find_elements(By.TAG_NAME, "a")
                    
                    tweet_id = None
                    for link in links:
                        href = link.get_attribute("href")
                        if href and "/status/" in href:
                            # Extract tweet ID
                            parts = href.split("/status/")
                            if len(parts) > 1:
                                tweet_id = parts[1].split("?")[0].split("/")[0]
                                break
                    
                    if not tweet_id:
                        continue
                    
                    # Skip if already seen
                    if self.last_tweet_id and int(tweet_id) <= int(self.last_tweet_id):
                        continue
                    
                    # Get tweet text
                    text_divs = article.find_elements(By.CSS_SELECTOR, "[data-testid='tweetText']")
                    text = ""
                    if text_divs:
                        text = text_divs[0].text[:280]
                    
                    if not text or len(text) < 3:
                        text = f"Tweet from @{TWITTER_USERNAME}"
                    
                    tweets.append({
                        'id': tweet_id,
                        'content': text,
                        'url': f"https://twitter.com/{TWITTER_USERNAME}/status/{tweet_id}",
                    })
                    
                except Exception as e:
                    continue
            
            print(f"✅ Extracted {len(tweets)} tweets")
            
            if tweets:
                self.save_last_tweet_id(tweets[0]["id"])
                return list(reversed(tweets))[:5]
            
            return []

        except Exception as e:
            print(f"❌ Error: {str(e)[:100]}")
            # Reinitialize driver on error
            self.close_driver()
            self.setup_driver()
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

            embed.set_footer(text="Twitter • Selenium")

            await self.channel.send(embed=embed)
            print(f"✅ Posted tweet {tweet['id']}")

        except Exception as e:
            print(f"❌ Error posting: {e}")

    async def close(self):
        self.close_driver()
        await super().close()


def validate_config():
    errors = []
    
    if not DISCORD_BOT_TOKEN:
        errors.append("DISCORD_BOT_TOKEN is required")
    if not DISCORD_CHANNEL_ID:
        errors.append("DISCORD_CHANNEL_ID is required")
    
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


if __name__ == "__main__":
    print("🚀 Starting Twitter to Discord bot (Selenium)...")
    
    if not validate_config():
        exit(1)
    
    bot = TwitterDiscordBot()
    bot.run(DISCORD_BOT_TOKEN)
