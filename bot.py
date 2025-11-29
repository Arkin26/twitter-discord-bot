import discord
from discord.ext import commands, tasks
import os
import requests
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# ----------------------------- EMBED SERVER URL -----------------------------

# Your Koyeb embed server
EMBED_SERVER_URL = "https://ridiculous-cindra-oknonononon-1d15a38f.koyeb.app"
if EMBED_SERVER_URL:
    EMBED_SERVER_URL = (
        f"https://{EMBED_SERVER_URL.strip()}"
        if "://" not in EMBED_SERVER_URL
        else EMBED_SERVER_URL
    )

# ----------------------------- DISCORD SETUP -----------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

POSTED_TWEETS_FILE = "posted_tweets.json"


# ----------------------------- LOAD/SAVE -----------------------------

def load_posted_tweets():
    if Path(POSTED_TWEETS_FILE).exists():
        try:
            return json.load(open(POSTED_TWEETS_FILE))
        except Exception:
            return {}
    return {}


def save_posted_tweets(data):
    json.dump(data, open(POSTED_TWEETS_FILE, "w"), indent=2)


# ----------------------------- VXTWITTER FALLBACK -----------------------------

def get_fxtwitter(username: str):
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
                    media_list.append(
                        {
                            "type": m.get("type"),  # "photo", "video", "gif"
                            "url": m.get("url"),
                            "preview_image_url": m.get("thumbnail_url"),
                            "video_url": m.get("url")
                            if m.get("type") in ["video", "gif"]
                            else None,
                        }
                    )

            tweets.append(
                {
                    "id": str(t["id"]),
                    "text": t["text"],
                    "url": t["url"],
                    "created_at": t.get("created_at", ""),
                    "metrics": t.get("stats", {}),  # likes, retweets, replies, views
                    "media": media_list,
                }
            )

        print("✅ vxtwitter fallback: tweets loaded.")
        return tweets

    except Exception as e:
        print(f"❌ vxtwitter fallback failed: {e}")
        return []


# ----------------------------- TWITTER API → INTERNAL FORMAT -----------------------------

def convert_official_to_internal(data, username: str):
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

            medias.append(
                {
                    "type": m.get("type"),  # "photo", "video", "animated_gif"
                    "url": m.get("url"),
                    "preview_image_url": m.get("preview_image_url"),
                    "video_url": video_url,
                }
            )

        tweets.append(
            {
                "id": t["id"],
                "text": t["text"],
                "url": f"https://x.com/{username}/status/{t['id']}",
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),  # like_count, retweet_count,...
                "media": medias,
            }
        )

    return tweets


def get_tweets(username: str):
    """
    Hybrid mode:
    1. Try Twitter API
    2. On 429 or error → fallback to vxtwitter
    """
    try:
        if not TWITTER_BEARER_TOKEN:
            print("⚠️ No Twitter API token — using vxtwitter fallback.")
            return get_fxtwitter(username)

        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
        max_retries = 3
        user_id = None

        # USER LOOKUP
        for attempt in range(max_retries):
            url = f"https://api.twitter.com/2/users/by/username/{username}"
            r = requests.get(url, headers=headers, timeout=10)

            if r.status_code == 429:
                print("⏳ Rate limited (user lookup) → using vxtwitter fallback.")
                return get_fxtwitter(username)

            if r.status_code != 200:
                print(
                    f"❌ Twitter user lookup failed [{r.status_code}] → vxtwitter fallback."
                )
                return get_fxtwitter(username)

            user_id = r.json()["data"]["id"]
            break

        if not user_id:
            print("⚠️ No user_id → vxtwitter fallback.")
            return get_fxtwitter(username)

        # FETCH TWEETS
        tweets_url = f"https://api.twitter.com/2/users/{user_id}/tweets"
        params = {
            "max_results": 5,
            "tweet.fields": "created_at,public_metrics",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "media_key,type,url,preview_image_url,variants,public_metrics",
        }

        for attempt in range(max_retries):
            r = requests.get(tweets_url, headers=headers, params=params, timeout=10)

            if r.status_code == 429:
                print("⏳ Rate limited (fetch tweets) → vxtwitter fallback.")
                return get_fxtwitter(username)

            if r.status_code != 200:
                print(f"❌ Twitter API returned {r.status_code} → vxtwitter fallback.")
                return get_fxtwitter(username)

            break

        return convert_official_to_internal(r.json(), username)

    except Exception as e:
        print(f"❌ Twitter API crashed ({e}) → vxtwitter fallback.")
        return get_fxtwitter(username)


# ----------------------------- POSTING -----------------------------

def extract_media(tweet):
    image_url = None
    video_url = None

    for m in tweet.get("media", []):
        m_type = m.get("type")
        if m_type == "photo":
            if not image_url:  # first photo
                image_url = m.get("url")
        elif m_type in ["video", "gif", "animated_gif"]:
            video_url = m.get("video_url")
            # preview image if available
            image_url = m.get("preview_image_url", image_url)

    return image_url, video_url


def extract_metrics(tweet):
    """Normalize metrics from either Twitter API or vxtwitter."""
    metrics = tweet.get("metrics", {}) or {}

    likes = (
        metrics.get("like_count")
        if "like_count" in metrics
        else metrics.get("likes", 0)
    )
    retweets = (
        metrics.get("retweet_count")
        if "retweet_count" in metrics
        else metrics.get("retweets", 0)
    )
    replies = (
        metrics.get("reply_count")
        if "reply_count" in metrics
        else metrics.get("replies", 0)
    )
    views = metrics.get("impression_count", metrics.get("views", 0))

    return likes, retweets, replies, views


async def post_one_tweet(tweet, channel, posted, force=False):

    if not force and tweet["id"] in posted:
        return

    image_url, video_url = extract_media(tweet)
    likes, retweets, replies, views = extract_metrics(tweet)

    # Build embed server link
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@NFL"
        f"&name=NFL"
        f"&handle=NFL"
        f"&text={quote(tweet['text'])}"
        f"&likes={likes}"
        f"&retweets={retweets}"
        f"&replies={replies}"
        f"&views={views}"
    )

    if image_url:
        embed_url += f"&image={quote(image_url)}"

    if video_url:
        embed_url += f"&video={quote(video_url)}"

    # Just send the URL – Discord will unfurl it using your Koyeb embed server
    await channel.send(embed_url)

    posted[tweet["id"]] = True
    print(f"✅ Posted tweet {tweet['id']}")


# ----------------------------- STARTUP FETCH -----------------------------

async def fetch_startup_tweets():
    """Always fetch top 2 tweets instantly using hybrid logic."""

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


# Check every 2 minutes instead of 1 to reduce 429
@tasks.loop(minutes=2)
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
    if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
        print("❌ Missing DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID")
    else:
        print("🚀 Starting Twitter bot...")
        bot.run(DISCORD_TOKEN)
