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

EMBED_SERVER_URL = "https://ridiculous-cindra-oknonononon-1d15a38f.koyeb.app/"
CDN_PROXY = "https://cdn.ahazek.org/get?url="

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------
# Fetch tweet using FixTweet API
# ---------------------------------------------------------

def fetch_tweet(tweet_id):
    url = f"https://api.fxtwitter.com/status/{tweet_id}"
    print("FETCHING:", url)

    r = requests.get(url, timeout=10)
    print("STATUS:", r.status_code)

    try:
        data = r.json()
    except:
        print("BAD JSON:", r.text)
        return None

    if "tweet" not in data:
        print("MISSING TWEET in response")
        return None

    return data["tweet"]


def fetch_latest_nfl():
    url = "https://api.fxtwitter.com/user/NFL"
    print("FETCH LATEST:", url)
    r = requests.get(url, timeout=10)

    try:
        data = r.json()
    except:
        return []

    return data.get("tweets", [])[:5]


# ---------------------------------------------------------
# Auto poster
# ---------------------------------------------------------

async def send_auto(tweet, channel):
    embed = discord.Embed(description=tweet["text"], color=0x1DA1F2)

    embed.set_author(
        name=f"{tweet['author']['name']} (@{tweet['author']['screen_name']})",
        url=f"https://x.com/{tweet['author']['screen_name']}/status/{tweet['id']}",
        icon_url=tweet["author"]["avatar_url"]
    )

    if tweet["media"].get("photos"):
        embed.set_image(url=tweet["media"]["photos"][0]["url"])

    await channel.send(embed=embed)

    if tweet["media"].get("videos"):
        raw = tweet["media"]["videos"][0]["url"]
        await channel.send(CDN_PROXY + quote(raw, safe=""))


async def startup():
    await bot.wait_until_ready()
    ch = bot.get_channel(DISCORD_CHANNEL_ID)
    tweets = fetch_latest_nfl()

    for t in tweets[:2]:
        await send_auto(t, ch)


# ---------------------------------------------------------
# !tweet command (FixTweet-style)
# ---------------------------------------------------------

TWEET_URL_REGEX = r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"

@bot.command()
async def tweet(ctx, url: str):
    match = re.search(TWEET_URL_REGEX, url)

    if not match:
        return await ctx.send("❌ Invalid Twitter/X link.")

    username = match.group(1)
    tweet_id = match.group(2)

    print("USERNAME EXTRACTED:", username)
    print("LOOKUP TWEET ID:", tweet_id)

    tweet = fetch_tweet(tweet_id)

    if not tweet:
        return await ctx.send("❌ Could not fetch tweet (maybe deleted or protected).")

    print("TWEET FETCH SUCCESS")

    text = tweet["text"]
    likes = tweet["likes"]
    retweets = tweet["retweets"]
    replies = tweet["replies"]
    views = tweet["views"]

    image_url = None
    video_url = None

    if tweet["media"].get("photos"):
        image_url = tweet["media"]["photos"][0]["url"]

    if tweet["media"].get("videos"):
        raw = tweet["media"]["videos"][0]["url"]
        video_url = CDN_PROXY + quote(raw, safe="")

    # Build FixTweet-style URL
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@{username}"
        f"&name={username}"
        f"&handle={username}"
        f"&text={quote(text)}"
        f"&likes={likes}"
        f"&retweets={retweets}"
        f"&replies={replies}"
        f"&views={views}"
    )

    if image_url:
        embed_url += "&image=" + quote(image_url)

    if video_url:
        embed_url += "&video=" + quote(video_url)

    print("EMBED_URL:", embed_url)

    await ctx.send(embed_url)


# ---------------------------------------------------------

@bot.event
async def on_ready():
    print("Logged in as:", bot.user)
    bot.loop.create_task(startup())

bot.run(DISCORD_TOKEN)
