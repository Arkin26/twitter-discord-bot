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

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

POSTED_TWEETS_FILE = "posted_tweets.json"


# ============================================================
# LOAD / SAVE
# ============================================================

def load_posted():
    if Path(POSTED_TWEETS_FILE).exists():
        try:
            return json.load(open(POSTED_TWEETS_FILE))
        except:
            return {}
    return {}

def save_posted(data):
    json.dump(data, open(POSTED_TWEETS_FILE, "w"), indent=2)


# ============================================================
# VXTwitter fallback
# ============================================================

def get_vx(username):
    try:
        r = requests.get(f"https://api.vxtwitter.com/user/{username}", timeout=10)
        if r.status_code != 200:
            print("VX error", r.status_code)
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
                "metrics": t.get("stats", {}),
                "media": media_list
            })

        print("Using VX fallback")
        return tweets

    except Exception as e:
        print("VX crash:", e)
        return []


# ============================================================
# TWITTER API (if available)
# ============================================================

def convert_tweets(data, username):
    media_map = {}
    if "includes" in data and "media" in data["includes"]:
        for m in data["includes"]["media"]:
            media_map[m["media_key"]] = m

    tweets = []

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
            "metrics": t.get("public_metrics", {}),
            "media": media_list
        })

    return tweets


def get_tweets(username):
    if not TWITTER_BEARER_TOKEN:
        return get_vx(username)

    try:
        headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

        # user lookup
        u = requests.get(
            f"https://api.twitter.com/2/users/by/username/{username}",
            headers=headers, timeout=10
        )

        if u.status_code != 200:
            return get_vx(username)

        user_id = u.json()["data"]["id"]

        # fetch tweets
        params = {
            "max_results": 5,
            "tweet.fields": "public_metrics,created_at",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,variants"
        }

        t = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            headers=headers, params=params, timeout=10
        )

        if t.status_code != 200:
            return get_vx(username)

        return convert_tweets(t.json(), username)

    except:
        return get_vx(username)


# ============================================================
# SEND EMBED
# ============================================================

async def send_tweet(tweet, channel, posted, force=False):
    if not force and tweet["id"] in posted:
        return

    media = tweet.get("media", [])
    image_url = None
    video_url = None

    for m in media:
        if m["type"] == "photo":
            image_url = m["url"]
        elif m["type"] in ["video", "animated_gif"]:
            video_url = m["video_url"]
            image_url = m.get("preview_image_url")

    # Build Discord embed (NO URL SEND)
    embed = discord.Embed(
        description=tweet["text"],
        color=0x1DA1F2
    )

    embed.set_author(
        name="NFL (@NFL)",
        url=tweet["url"],
        icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png"
    )

    stats = tweet["metrics"]
    embed.add_field(name="💬", value=stats.get("reply_count", 0), inline=True)
    embed.add_field(name="🔁", value=stats.get("retweet_count", 0), inline=True)
    embed.add_field(name="❤️", value=stats.get("like_count", 0), inline=True)
    embed.add_field(name="👁", value=stats.get("impression_count", 0), inline=True)

    if image_url:
        embed.set_image(url=image_url)

    await channel.send(embed=embed)

    if video_url:
        await channel.send(video_url)

    posted[tweet["id"]] = True
    print("Posted", tweet["id"])


# ============================================================
# BOT EVENTS
# ============================================================

async def startup():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    if not ch:
        print("No channel")
        return

    tweets = get_tweets("NFL")
    posted = load_posted()

    for t in tweets[:2]:
        await send_tweet(t, ch, posted, force=True)

    save_posted(posted)


@bot.event
async def on_ready():
    print("Logged in as:", bot.user)
    await startup()
    tweet_loop.start()


@tasks.loop(minutes=1)
async def tweet_loop():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    posted = load_posted()

    tweets = get_tweets("NFL")
    for t in tweets:
        await send_tweet(t, ch, posted)

    save_posted(posted)


bot.run(DISCORD_TOKEN)
