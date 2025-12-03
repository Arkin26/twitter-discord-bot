import discord
from discord.ext import commands, tasks
import os
import requests
import json
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
import re

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# FIXTWEET ARCHITECTURE
EMBED_SERVER_URL = "https://ridiculous-cindra-oknonononon-1d15a38f.koyeb.app/"
CDN_PROXY = "https://cdn.ahazek.org/get?url="

# REQUIRED FOR TWITTER + VX
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

POSTED_TWEETS_FILE = "posted_tweets.json"


# ============================================================
# HELPERS
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
# VX Fallback
# ============================================================

def get_vx(username):
    try:
        r = requests.get(
            f"https://api.vxtwitter.com/user/{username}",
            timeout=10,
            headers=HEADERS
        )
        if r.status_code != 200:
            return []

        data = r.json()
        tweets = []

        for t in data.get("tweets", [])[:5]:
            media = []
            for m in t.get("media", []):
                media.append({
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
                "media": media
            })

        return tweets

    except:
        return []


# ============================================================
# TWITTER API
# ============================================================

def convert_tweets(data, username):
    media_map = {}

    if "includes" in data and "media" in data["includes"]:
        for m in data["includes"]["media"]:
            media_map[m["media_key"]] = m

    tweets = []

    for t in data.get("data", []):
        media = []
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

            media.append({
                "type": m.get("type"),
                "url": m.get("url"),
                "preview_image_url": m.get("preview_image_url"),
                "video_url": video_url
            })

        tweets.append({
            "id": str(t["id"]),  # ALWAYS STRING
            "text": t["text"],
            "url": f"https://x.com/{username}/status/{t['id']}",
            "metrics": t.get("public_metrics", {}),
            "media": media
        })

    return tweets


def get_tweets(username):
    if not TWITTER_BEARER_TOKEN:
        return get_vx(username)

    try:
        auth_headers = {
            **HEADERS,
            "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"
        }

        # Lookup user
        u = requests.get(
            f"https://api.twitter.com/2/users/by/username/{username}",
            headers=auth_headers,
            timeout=10
        )

        if u.status_code != 200:
            return get_vx(username)

        user_id = u.json()["data"]["id"]

        params = {
            "max_results": 5,
            "tweet.fields": "public_metrics",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,variants"
        }

        # Fetch tweets
        t = requests.get(
            f"https://api.twitter.com/2/users/{user_id}/tweets",
            headers=auth_headers,
            params=params,
            timeout=10
        )

        if t.status_code != 200:
            return get_vx(username)

        return convert_tweets(t.json(), username)

    except:
        return get_vx(username)


# ============================================================
# AUTO POST (works fine)
# ============================================================

async def send_tweet(tweet, channel, posted, force=False):
    if not force and tweet["id"] in posted:
        return

    image_url = None
    video_url = None

    for m in tweet.get("media", []):
        if m["type"] == "photo":
            image_url = m["url"]
        elif m["type"] in ["video", "animated_gif", "gif"]:
            video_url = m["video_url"]
            image_url = m.get("preview_image_url", image_url)

    embed = discord.Embed(description=tweet["text"], color=0x1DA1F2)
    embed.set_author(name="NFL (@NFL)", url=tweet["url"],
                     icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png")

    stats = tweet["metrics"]
    embed.add_field(name="💬", value=stats.get("reply_count", 0))
    embed.add_field(name="🔁", value=stats.get("retweet_count", 0))
    embed.add_field(name="❤️", value=stats.get("like_count", 0))
    embed.add_field(name="👁", value=stats.get("impression_count", 0))

    if image_url:
        embed.set_image(url=image_url)

    await channel.send(embed=embed)

    if video_url:
        proxied = CDN_PROXY + quote(video_url, safe="")
        await channel.send(proxied)

    posted[tweet["id"]] = True
    save_posted(posted)


# ============================================================
# STARTUP
# ============================================================

async def startup():
    await bot.wait_until_ready()

    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    if not ch:
        print("Channel not found")
        return

    tweets = get_tweets("NFL")
    posted = load_posted()

    for t in tweets[:2]:
        await send_tweet(t, ch, posted, force=True)

    save_posted(posted)


@bot.event
async def on_ready():
    print("Logged in as:", bot.user)
    bot.loop.create_task(startup())
    tweet_loop.start()


@tasks.loop(minutes=1)
async def tweet_loop():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    posted = load_posted()
    tweets = get_tweets("NFL")

    for t in tweets:
        await send_tweet(t, ch, posted)

    save_posted(posted)


# ============================================================
# !tweet COMMAND (FULL FIXTWEET STYLE)
# ============================================================

TWEET_URL_REGEX = r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"

@bot.command()
async def tweet(ctx, url: str):
    match = re.search(TWEET_URL_REGEX, url)
    if not match:
        return await ctx.send("❌ Invalid Twitter/X link.")

    username = match.group(1)
    tweet_id = match.group(2)

    print("USERNAME EXTRACTED:", username)
    print("TWEET ID:", tweet_id)

    tweets = get_tweets(username)
    print("FOUND TWEET IDS:", [str(t["id"]) for t in tweets])

    # FIXED STRING ID MATCH
    target = next((t for t in tweets if str(t["id"]) == str(tweet_id)), None)

    if not target:
        return await ctx.send("❌ Tweet not found.")

    image_url = None
    video_url = None

    for m in target.get("media", []):
        if m["type"] == "photo":
            image_url = m["url"]
        elif m["type"] in ["video", "animated_gif", "gif"]:
            raw = m.get("video_url")
            if raw:
                video_url = CDN_PROXY + quote(raw, safe="")
            image_url = m.get("preview_image_url", image_url)

    # Build embed URL
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@{username}"
        f"&name={username}"
        f"&handle={username}"
        f"&text={quote(target['text'])}"
        f"&likes={target['metrics'].get('like_count', 0)}"
        f"&retweets={target['metrics'].get('retweet_count', 0)}"
        f"&replies={target['metrics'].get('reply_count', 0)}"
        f"&views={target['metrics'].get('impression_count', 0)}"
    )

    if image_url:
        embed_url += "&image=" + quote(image_url)

    if video_url:
        embed_url += "&video=" + quote(video_url)

    print("EMBED_URL:", embed_url)
    await ctx.send(embed_url)


bot.run(DISCORD_TOKEN)
