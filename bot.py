import os
import re
import json
import requests
from urllib.parse import quote
from pathlib import Path

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))

# Your domains
EMBED_SERVER_URL = "https://embed.ahazek.org/"
CDN_PROXY = "https://cdn.ahazek.org/get?url="

POSTED_TWEETS_FILE = "posted_tweets.json"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ============================================================
# UTILS: LOAD / SAVE POSTED IDS
# ============================================================

def load_posted():
    if Path(POSTED_TWEETS_FILE).exists():
        try:
            return json.load(open(POSTED_TWEETS_FILE))
        except Exception:
            return {}
    return {}


def save_posted(data):
    json.dump(data, open(POSTED_TWEETS_FILE, "w"), indent=2)


# ============================================================
# FXTWITTER HELPERS
# ============================================================

FX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape_fxtwitter_mp4(tweet_id: str):
    """
    Fallback: scrape https://fxtwitter.com/i/status/<id>
    and extract first video .mp4 URL.
    """
    url = f"https://fxtwitter.com/i/status/{tweet_id}"
    print("SCRAPE HTML:", url)
    try:
        r = requests.get(url, headers=FX_HEADERS, timeout=10)
        print("SCRAPE STATUS:", r.status_code)
        if r.status_code != 200:
            return None

        # Look for https://video.twimg.com/...mp4
        m = re.search(r'(https://video\.twimg\.com/[^\"]+\.mp4)', r.text)
        if m:
            mp4 = m.group(1)
            print("FOUND MP4:", mp4)
            return mp4

        print("NO MP4 FOUND IN HTML")
        return None

    except Exception as e:
        print("SCRAPE ERROR:", e)
        return None


def fetch_fx_status(tweet_id: str):
    """
    Fetch tweet details from FXTwitter status JSON.
    We only trust it for text + counters + photos.
    """
    url = f"https://api.fxtwitter.com/status/{tweet_id}"
    print("FETCH STATUS JSON:", url)

    try:
        r = requests.get(url, headers=FX_HEADERS, timeout=10)
        print("STATUS JSON CODE:", r.status_code)
        if r.status_code != 200:
            return None

        data = r.json()
    except Exception as e:
        print("STATUS JSON ERROR:", e)
        return None

    tweet = data.get("tweet") or {}
    media = data.get("media") or {}

    out = {
        "text": tweet.get("text", ""),
        "likes": tweet.get("likes", 0),
        "retweets": tweet.get("retweets", 0),
        "replies": tweet.get("replies", 0),
        "views": tweet.get("views", 0),
        "image": None,  # thumbnail
    }

    # Try to get a photo thumbnail if present
    if isinstance(media, dict):
        photos = media.get("photos") or []
        if isinstance(photos, list) and photos:
            first = photos[0]
            if isinstance(first, dict):
                out["image"] = first.get("url")

    return out


def fetch_user_tweets(username: str):
    """
    For auto-posting: get latest tweets from a user via FXTwitter.
    """
    url = f"https://api.fxtwitter.com/user/{username}"
    print("FETCH USER TWEETS:", url)

    try:
        r = requests.get(url, headers=FX_HEADERS, timeout=10)
        print("USER JSON CODE:", r.status_code)
        if r.status_code != 200:
            return []

        data = r.json()
    except Exception as e:
        print("USER JSON ERROR:", e)
        return []

    tweets = []
    for t in data.get("tweets", [])[:5]:
        media_thumb = None
        media = t.get("media") or []
        if isinstance(media, list):
            for m in media:
                if isinstance(m, dict) and m.get("type") == "photo":
                    media_thumb = m.get("url")
                    break

        tweets.append({
            "id": str(t.get("id")),
            "text": t.get("text", ""),
            "url": t.get("url"),
            "stats": t.get("stats", {}),
            "thumb": media_thumb,
        })

    return tweets


# ============================================================
# AUTO-POSTING: SEND SIMPLE EMBED (NO CUSTOM HTML)
# ============================================================

async def send_auto(tweet, channel, posted, force=False):
    if not force and tweet["id"] in posted:
        return

    embed = discord.Embed(description=tweet["text"], color=0x1DA1F2)

    embed.set_author(
        name="NFL (@NFL)",
        url=tweet["url"],
        icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
    )

    stats = tweet.get("stats", {})
    embed.add_field(name="💬", value=stats.get("replies", 0))
    embed.add_field(name="🔁", value=stats.get("retweets", 0))
    embed.add_field(name="❤️", value=stats.get("likes", 0))
    embed.add_field(name="👁", value=stats.get("views", 0))

    if tweet["thumb"]:
        embed.set_image(url=tweet["thumb"])

    await channel.send(embed=embed)

    posted[tweet["id"]] = True
    save_posted(posted)


# ============================================================
# STARTUP + LOOP
# ============================================================

async def startup():
    await bot.wait_until_ready()
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    if not ch:
        print("CHANNEL NOT FOUND")
        return

    posted = load_posted()
    tweets = fetch_user_tweets("NFL")

    # Always post top 2 on restart
    for t in tweets[:2]:
        await send_auto(t, ch, posted, force=True)

    save_posted(posted)


@bot.event
async def on_ready():
    print("Logged in as:", bot.user)
    bot.loop.create_task(startup())
    tweet_loop.start()


@tasks.loop(minutes=1)
async def tweet_loop():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    if not ch:
        print("CHANNEL NOT FOUND (loop)")
        return

    posted = load_posted()
    tweets = fetch_user_tweets("NFL")

    for t in tweets:
        await send_auto(t, ch, posted)

    save_posted(posted)


# ============================================================
# !tweet COMMAND — FULL FIXTWEET STYLE
# ============================================================

TWEET_URL_REGEX = r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"

@bot.command()
async def tweet(ctx, url: str):
    match = re.search(TWEET_URL_REGEX, url)
    if not match:
        return await ctx.send("❌ Invalid X/Twitter link.")

    username = match.group(1)
    tweet_id = match.group(2)

    print("USERNAME:", username)
    print("LOOKUP TWEET ID:", tweet_id)

    # 1) Text + counters + (maybe) image from FXTwitter JSON
    info = fetch_fx_status(tweet_id)
    if not info:
        return await ctx.send("❌ Could not fetch tweet data.")

    # 2) Always try HTML scrape for video
    mp4 = scrape_fxtwitter_mp4(tweet_id)

    image_url = info["image"]
    video_url = None

    if mp4:
        video_url = CDN_PROXY + quote(mp4, safe="")

    # 3) Build embed server URL
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@{username}"
        f"&text={quote(info['text'])}"
        f"&likes={info['likes']}"
        f"&retweets={info['retweets']}"
        f"&replies={info['replies']}"
        f"&views={info['views']}"
    )

    if image_url:
        embed_url += "&image=" + quote(image_url)

    if video_url:
        embed_url += "&video=" + quote(video_url)

    print("EMBED_URL:", embed_url)
    await ctx.send(embed_url)


# ============================================================
# RUN BOT
# ============================================================

bot.run(DISCORD_TOKEN)
