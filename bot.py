import discord
from discord.ext import commands, tasks
import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv
import re

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
EMBED_SERVER_URL = "https://embed.ahazek.org/"
CDN_PROXY = "https://cdn.ahazek.org/get?url="

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# Fetch tweet from FXTwitter by ID (MOST RELIABLE)
# ---------------------------------------------------------
def fetch_tweet_by_id(tweet_id):
    url = f"https://api.fxtwitter.com/status/{tweet_id}"
    print("FETCH:", url)

    r = requests.get(url, timeout=10)
    print("STATUS:", r.status_code)

    if r.status_code != 200:
        return None

    data = r.json()
    print("TWEET FETCH SUCCESS")

    return data.get("tweet")


# ---------------------------------------------------------
# Build embed-server URL (FixTweet style)
# ---------------------------------------------------------
def build_embed_url(tweet):
    username = tweet["author"]["screen_name"]
    text = tweet["text"]

    likes = tweet["stats"]["likes"]
    retweets = tweet["stats"]["retweets"]
    replies = tweet["stats"]["replies"]
    views = tweet["stats"].get("views", 0)

    # Find media
    image_url = None
    video_url = None

    if tweet.get("media"):
        for m in tweet["media"]:
            if m["type"] == "photo":
                image_url = m["url"]
            elif m["type"] == "video":
                # proxy the video
                raw = m["variants"][0]["url"]
                video_url = CDN_PROXY + quote(raw, safe="")

    # build link
    url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@{username}"
        f"&text={quote(text)}"
        f"&likes={likes}"
        f"&retweets={retweets}"
        f"&replies={replies}"
        f"&views={views}"
    )

    if image_url:
        url += "&image=" + quote(image_url)

    if video_url:
        url += "&video=" + quote(video_url)

    print("EMBED_URL:", url)
    return url


# ---------------------------------------------------------
# AUTO FETCH LATEST TWEET FROM NFL
# ---------------------------------------------------------
def get_latest_nfl_tweet():
    url = "https://api.fxtwitter.com/user/NFL"
    print("FETCH LATEST:", url)

    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        print("LATEST ERROR:", r.status_code)
        return None

    data = r.json()
    tweets = data.get("tweets")

    if not tweets:
        print("NO TWEETS FOUND")
        return None

    return tweets[0]  # newest tweet


# ---------------------------------------------------------
# STARTUP EVENT
# ---------------------------------------------------------
async def startup():
    await bot.wait_until_ready()
    ch = bot.get_channel(DISCORD_CHANNEL_ID)

    t = get_latest_nfl_tweet()
    if not t:
        return

    embed_url = build_embed_url(t)
    await ch.send(embed_url)


@bot.event
async def on_ready():
    print("Logged in as:", bot.user)
    bot.loop.create_task(startup())
    tweet_loop.start()


# ---------------------------------------------------------
# LOOP (check every 1 minute)
# ---------------------------------------------------------
@tasks.loop(minutes=1)
async def tweet_loop():
    ch = bot.get_channel(DISCORD_CHANNEL_ID)

    t = get_latest_nfl_tweet()
    if not t:
        return

    embed_url = build_embed_url(t)
    await ch.send(embed_url)


# ---------------------------------------------------------
# !tweet COMMAND
# ---------------------------------------------------------
TWEET_URL_REGEX = r"(?:twitter\.com|x\.com)/[^/]+/status/(\d+)"

@bot.command()
async def tweet(ctx, url: str):
    match = re.search(TWEET_URL_REGEX, url)
    if not match:
        return await ctx.send("❌ Invalid Tweet URL")

    tweet_id = match.group(1)
    print("LOOKUP TWEET:", tweet_id)

    t = fetch_tweet_by_id(tweet_id)
    if not t:
        return await ctx.send("❌ Could not fetch tweet")

    embed_url = build_embed_url(t)
    await ctx.send(embed_url)


bot.run(DISCORD_TOKEN)
