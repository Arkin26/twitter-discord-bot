import discord
from discord.ext import commands, tasks
import os
import requests
import json
from urllib.parse import quote
from pathlib import Path
from dotenv import load_dotenv
import re

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))

EMBED_SERVER_URL = "https://embed.ahazek.org/"
CDN_PROXY = "https://cdn.ahazek.org/get?url="

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ============================================================
# HELPER
# ============================================================

def get_fx_tweet(tweet_id):
    url = f"https://api.fxtwitter.com/status/{tweet_id}"
    print("FETCHING:", url)

    r = requests.get(url, timeout=10)
    print("STATUS:", r.status_code)

    if r.status_code != 200:
        return None

    data = r.json()
    print("TWEET FETCH SUCCESS")

    # FXTwitter returns this:
    # { "tweet": {...}, "media": {...} }
    if "tweet" not in data:
        return None

    tweet = data["tweet"]

    # Normalize media
    media_list = []

    if "media" in data and isinstance(data["media"], dict):
        # photos
        for p in data["media"].get("photos", []):
            media_list.append({
                "type": "photo",
                "url": p.get("url")
            })

        # videos
        for v in data["media"].get("videos", []):
            media_list.append({
                "type": "video",
                "url": v.get("url"),
                "preview": v.get("thumbnail_url")
            })

    # normalized return
    return {
        "id": str(tweet_id),
        "text": tweet.get("text", ""),
        "likes": tweet.get("likes", 0),
        "replies": tweet.get("replies", 0),
        "retweets": tweet.get("retweets", 0),
        "views": tweet.get("views", 0),
        "media": media_list
    }


# ============================================================
# COMMAND
# ============================================================

TWEET_URL_REGEX = r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"

@bot.command()
async def tweet(ctx, url: str):
    match = re.search(TWEET_URL_REGEX, url)
    if not match:
        return await ctx.send("❌ Invalid link")

    username = match.group(1)
    tweet_id = match.group(2)

    print("USERNAME:", username)
    print("LOOKUP TWEET ID:", tweet_id)

    data = get_fx_tweet(tweet_id)
    if not data:
        return await ctx.send("❌ Tweet fetch failed")

    # get media
    image_url = None
    video_url = None

    for m in data["media"]:
        if m["type"] == "photo" and not image_url:
            image_url = m["url"]
        if m["type"] == "video" and not video_url:
            video_url = CDN_PROXY + quote(m["url"], safe="")
            image_url = m.get("preview", image_url)

    # build embed server URL
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@{username}"
        f"&text={quote(data['text'])}"
        f"&likes={data['likes']}"
        f"&retweets={data['retweets']}"
        f"&replies={data['replies']}"
        f"&views={data['views']}"
    )

    if image_url:
        embed_url += "&image=" + quote(image_url)

    if video_url:
        embed_url += "&video=" + quote(video_url)

    print("EMBED_URL:", embed_url)
    await ctx.send(embed_url)



# ============================================================
# RUN
# ============================================================

bot.run(DISCORD_TOKEN)
