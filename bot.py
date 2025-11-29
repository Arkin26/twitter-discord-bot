import discord
from discord.ext import commands, tasks
import os
import requests
import json
import asyncio
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# Embed server URL
EMBED_SERVER_URL = os.getenv('REPLIT_DOMAINS', '').split(',')[0].strip() if os.getenv('REPLIT_DOMAINS') else 'localhost:5000'
if EMBED_SERVER_URL:
    EMBED_SERVER_URL = f"https://{EMBED_SERVER_URL.strip()}" if "://" not in EMBED_SERVER_URL else EMBED_SERVER_URL

# Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Tracking posted tweets
POSTED_TWEETS_FILE = "posted_tweets.json"


# ----------------------------- LOAD/SAVE -----------------------------

def load_posted_tweets():
    if Path(POSTED_TWEETS_FILE).exists():
        try:
            return json.load(open(POSTED_TWEETS_FILE))
        except:
            return {}
    return {}


def save_posted_tweets(data):
    json.dump(data, open(POSTED_TWEETS_FILE, "w"), indent=2)


# ----------------------------- FIXTWEET FALLBACK -----------------------------

def get_fxtwitter(username):
            """Reliable fallback using vxtwitter API."""
            try:
                url = f"https://api.vxtwitter.com/user/{username}"
                r = requests.get(url, timeout=10)

                if r.status_code != 200:
                    print(f"❌ vxtwitter API returned status {r.status_code}")
                    return []

                data = r.json()

                tweets = []

                for t in data.get("tweets", [])[:5]:
                    media_list = []

                    if t.get("media"):
                        for m in t["media"]:
                            media_list.append({
                                "type": m.get("type"),
                                "url": m.get("url"),
                                "preview_image_url": m.get("thumbnail_url"),
                                "video_url": m.get("url") if m.get("type") in ["video", "gif"] else None
                            })

                    tweets.append({
                        "id": str(t["id"]),
                        "text": t["text"],
                        "url": t["url"],
                        "created_at": t.get("created_at", ""),
                        "metrics": t.get("stats", {}),
                        "media": media_list
                    })

                print("✅ vxtwitter fallback: tweets loaded.")
                return tweets

            except Exception as e:
                print(f"❌ vxtwitter fallback failed: {e}")
                return []



# ----------------------------- TWITTER API FETCH -----------------------------

def convert_official_to_internal(data, username):
    """Convert Twitter API JSON → our internal tweet format."""
    tweets = []
    media_dict = {}

    if "includes" in data and "media" in data["includes"]:
        for m in data["includes"]["media"]:
            media_dict[m["media_key"]] = m

    for t in data.get("data", []):
        medias = []

        for key in t.get("attachments", {}).get("media_keys", []):
            m = media_dict.get(key)
            if not m:
                continue

            video_url = None
            if m.get("type") in ["video", "animated_gif"] and "variants" in m:
                for v in m["variants"]:
                    if v.get("content_type") == "video/mp4":
                        video_url = v["url"]
                        break

            medias.append({
                "type": m.get("type"),
                "url": m.get("url"),
                "preview_image_url": m.get("preview_image_url"),
                "video_url": video_url
            })

        tweets.append({
            "id": t["id"],
            "text": t["text"],
            "url": f"https://x.com/{username}/status/{t['id']}",
            "created_at": t.get("created_at", ""),
            "metrics": t.get("public_metrics", {}),
            "media": medias
        })

    return tweets


def get_tweets(username):
    """Try Twitter API → if failing, use FixTweet fallback."""
    try:
        if not TWITTER_BEARER_TOKEN:
            print("⚠️ No Twitter API token — using FixTweet fallback.")
            return get_fxtwitter(username)

        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
        max_retries = 3
        user_id = None

        # USER LOOKUP
        for attempt in range(max_retries):
            url = f"https://api.twitter.com/2/users/by/username/{username}"
            r = requests.get(url, headers=headers, timeout=10)

            if r.status_code == 429:
                print("⏳ Rate limited (user lookup) → using FixTweet fallback.")
                return get_fxtwitter(username)

            if r.status_code != 200:
                print(f"❌ Twitter user lookup failed [{r.status_code}] → FixTweet fallback.")
                return get_fxtwitter(username)

            user_id = r.json()["data"]["id"]
            break

        if not user_id:
            print("⚠️ No user_id → FixTweet fallback.")
            return get_fxtwitter(username)

        # FETCH TWEETS
        tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        params = {
            "max_results": 5,
            "tweet.fields": "created_at,public_metrics",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "media_key,type,url,preview_image_url,variants,public_metrics"
        }

        for attempt in range(max_retries):
            r = requests.get(tweets_url, headers=headers, params=params, timeout=10)

            if r.status_code == 429:
                print("⏳ Rate limited (fetch tweets) → FixTweet fallback.")
                return get_fxtwitter(username)

            if r.status_code != 200:
                print(f"❌ Twitter API returned {r.status_code} → FixTweet fallback.")
                return get_fxtwitter(username)

            break

        return convert_official_to_internal(r.json(), username)

    except Exception as e:
        print(f"❌ Twitter API crashed ({e}) → FixTweet fallback.")
        return get_fxtwitter(username)


# ----------------------------- POSTING -----------------------------

async def post_one_tweet(tweet, channel, posted, force=False):

    if not force and tweet["id"] in posted:
        return

    image_url = None
    video_url = None

    if tweet["media"]:
        for m in tweet["media"]:
            if m["type"] == "photo":
                image_url = m.get("url")
            elif m["type"] in ["video", "gif", "animated_gif"]:
                video_url = m.get("video_url")
                image_url = m.get("preview_image_url", image_url)

    # Build embed server link
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@NFL&name=NFL&handle=NFL"
        f"&text={quote(tweet['text'])}"
        f"&likes={tweet['metrics'].get('likes', 0)}"
        f"&retweets={tweet['metrics'].get('retweets', 0)}"
        f"&replies={tweet['metrics'].get('replies', 0)}"
        f"&views={tweet['metrics'].get('views', 0)}"
    )

    if image_url:
        embed_url += f"&image={quote(image_url)}"
    if video_url:
        embed_url += f"&video={quote(video_url)}"

    embed = discord.Embed(description=f"[View Tweet]({tweet['url']})", color=0x1F51BA)
    embed.set_author(name="@NFL", url=tweet["url"])

    embed.set_image(url=image_url) if image_url else None
    embed.set_video(url=video_url) if video_url else None

    embed.set_footer(text="X.com")

    await channel.send(content=embed_url, embed=embed)

    posted[tweet["id"]] = True
    print(f"✅ Posted tweet {tweet['id']}")


# ----------------------------- STARTUP FETCH -----------------------------

async def fetch_startup_tweets():
    """Always fetch top 2 tweets instantly using fallback if needed."""

    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print("❌ No channel found.")
        return

    print("📌 Fetching top 2 tweets instantly...")

    tweets = get_tweets("NFL")

    if not tweets:
        print("⚠️ No tweets found at startup.")
        return

    posted = load_posted_tweets()

    for t in tweets[:2]:
        await post_one_tweet(t, channel, posted, force=True)

    save_posted_tweets(posted)


# ----------------------------- DISCORD EVENTS -----------------------------

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    await fetch_startup_tweets()

    if not tweet_checker.is_running():
        tweet_checker.start()
        print("🔄 Tweet checker started")


@tasks.loop(minutes=1)
async def tweet_checker():
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        return

    posted = load_posted_tweets()
    tweets = get_tweets("NFL")

    if tweets:
        for t in tweets:
            await post_one_tweet(t, channel, posted, force=False)

        save_posted_tweets(posted)
    else:
        print("ℹ️ No tweets found this cycle.")


@tweet_checker.before_loop
async def before_loop():
    await bot.wait_until_ready()


# ----------------------------- START BOT -----------------------------

if __name__ == "__main__":
    print("🚀 Starting Twitter bot...")
    bot.run(DISCORD_TOKEN)
