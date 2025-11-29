import discord
from discord.ext import commands, tasks
import os
import requests
import json
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# Your embed server URL (Koyeb)
EMBED_SERVER_URL = os.getenv("APP_URL").strip()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

POSTED_TWEETS_FILE = "posted_tweets.json"


# ---------------------------------------------------------
# DATA STORE
# ---------------------------------------------------------

def load_posted_tweets():
    if Path(POSTED_TWEETS_FILE).exists():
        try:
            return json.load(open(POSTED_TWEETS_FILE))
        except:
            return {}
    return {}

def save_posted_tweets(data):
    json.dump(data, open(POSTED_TWEETS_FILE, "w"), indent=2)


# ---------------------------------------------------------
# FIXTWEET FALLBACK
# ---------------------------------------------------------

def get_fxtwitter(username):
    try:
        r = requests.get(f"https://api.vxtwitter.com/user/{username}", timeout=10)
        if r.status_code != 200:
            print(f"❌ vxtwitter error: {r.status_code}")
            return []

        data = r.json()
        out = []

        for t in data.get("tweets", [])[:5]:
            media = []
            for m in t.get("media", []):
                media.append({
                    "type": m.get("type"),
                    "url": m.get("url"),
                    "preview_image_url": m.get("thumbnail_url"),
                    "video_url": m.get("url") if m.get("type") in ["video", "gif"] else None
                })

            out.append({
                "id": str(t["id"]),
                "text": t["text"],
                "url": t["url"],
                "created_at": t.get("created_at", ""),
                "metrics": t.get("stats", {}),
                "media": media
            })

        print("✅ Using FixTweet fallback")
        return out

    except Exception as e:
        print("❌ fallback crashed:", e)
        return []


# ---------------------------------------------------------
# TWITTER API FETCH
# ---------------------------------------------------------

def convert_official_to_internal(data, username):
    tweets = []
    media_map = {}

    if "includes" in data and "media" in data["includes"]:
        for m in data["includes"]["media"]:
            media_map[m["media_key"]] = m

    for t in data.get("data", []):
        media_list = []

        for key in t.get("attachments", {}).get("media_keys", []):
            m = media_map.get(key)
            if not m:
                continue

            video_url = None
            if m.get("type") in ["video", "animated_gif"]:
                for v in m.get("variants", []):
                    if v.get("content_type") == "video/mp4":
                        video_url = v["url"]
                        break

            media_list.append({
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
            "media": media_list
        })

    return tweets


def get_tweets(username):
    if not TWITTER_BEARER_TOKEN:
        print("⚠ No Twitter API — using fallback")
        return get_fxtwitter(username)

    try:
        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

        # USER LOOKUP
        u = requests.get(
            f"https://api.twitter.com/2/users/by/username/{username}",
            headers=headers, timeout=10
        )

        if u.status_code == 429:
            print("⏳ rate limit user lookup → fallback")
            return get_fxtwitter(username)

        if u.status_code != 200:
            print(f"⚠ user lookup failed {u.status_code} → fallback")
            return get_fxtwitter(username)

        user_id = u.json()["data"]["id"]

        # FETCH TWEETS
        params = {
            "max_results": 5,
            "tweet.fields": "created_at,public_metrics",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "media_key,type,url,preview_image_url,variants"
        }

        t = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            headers=headers, params=params, timeout=10
        )

        if t.status_code == 429:
            print("⏳ tweet fetch rate-limited → fallback")
            return get_fxtwitter(username)

        if t.status_code != 200:
            print(f"⚠ tweet fetch failed → fallback {t.status_code}")
            return get_fxtwitter(username)

        return convert_official_to_internal(t.json(), username)

    except Exception as e:
        print("❌ Twitter API exception → fallback:", e)
        return get_fxtwitter(username)


# ---------------------------------------------------------
# POST TWEET TO DISCORD
# ---------------------------------------------------------

async def post_one_tweet(tweet, channel, posted, force=False):
    if not force and tweet["id"] in posted:
        return

    image_url = None
    video_url = None

    # Pick media
    for m in tweet.get("media", []):
        if m["type"] == "photo":
            image_url = m["url"]
        elif m["type"] in ["video", "gif", "animated_gif"]:
            video_url = m["video_url"]
            image_url = m.get("preview_image_url", image_url)

    # ---- Build Discord Embed ----
    embed = discord.Embed(
        description=tweet["text"],
        color=0x1DA1F2  # Twitter blue
    )

    embed.set_author(
        name="NFL (@NFL)",
        url=tweet["url"],
        icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
    )

    # Add stats
    stats = tweet["metrics"]
    embed.add_field(
        name="💬 Replies",
        value=stats.get("reply_count", 0),
        inline=True
    )
    embed.add_field(
        name="🔁 Retweets",
        value=stats.get("retweet_count", 0),
        inline=True
    )
    embed.add_field(
        name="❤️ Likes",
        value=stats.get("like_count", 0),
        inline=True
    )
    embed.add_field(
        name="👁 Views",
        value=stats.get("impression_count", 0),
        inline=True
    )

    # Image / Video
    if image_url:
        embed.set_image(url=image_url)

    # For video — Discord needs the URL directly, not inside embed
    if video_url:
        await channel.send(video_url)

    # Send the embed
    await channel.send(embed=embed)

    # Mark as posted
    posted[tweet["id"]] = True
    print("Posted", tweet["id"])



# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

async def fetch_startup_tweets():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    if not ch:
        print("❌ Invalid channel ID")
        return

    print("Fetching startup tweets...")

    tweets = get_tweets("NFL")
    posted = load_posted_tweets()

    for t in tweets[:2]:
        await post_one_tweet(t, ch, posted, force=True)

    save_posted_tweets(posted)


# ---------------------------------------------------------
# LOOP
# ---------------------------------------------------------

@bot.event
async def on_ready():
    print("Bot logged in as", bot.user)
    await fetch_startup_tweets()
    tweet_checker.start()

@tasks.loop(minutes=1)
async def tweet_checker():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    posted = load_posted_tweets()

    tweets = get_tweets("NFL")
    if not tweets:
        print("No tweets found.")
        return

    for t in tweets:
        await post_one_tweet(t, ch, posted)

    save_posted_tweets(posted)


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

bot.run(DISCORD_TOKEN)
