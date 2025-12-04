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

# FIXTWEET ARCHITECTURE
EMBED_SERVER_URL = "https://ridiculous-cindra-oknonononon-1d15a38f.koyeb.app/"
CDN_PROXY = "https://cdn.ahazek.org/get?url="

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

POSTED_TWEETS_FILE = "posted_tweets.json"


# ============================================================
# UTIL
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
# FETCH TWEET BY ID — FIXTWEET API (100% RELIABLE)
# ============================================================

def fetch_tweet_by_id(tweet_id: str):
    url = f"https://api.fxtwitter.com/status/{tweet_id}"
    print("FETCHING:", url)

    try:
        r = requests.get(url, timeout=10)
        print("STATUS:", r.status_code)

        if r.status_code != 200:
            print("ERROR:", r.text)
            return None

        data = r.json()

        if "tweet" not in data:
            print("INVALID RESPONSE:", data)
            return None

        t = data["tweet"]

        # Parse media
        media_list = []
        for m in t.get("media", []):
            media_list.append({
                "type": m.get("type"),
                "url": m.get("url"),
                "preview": m.get("thumbnail_url"),
                "variants": m.get("variants", [])
            })

        hd_video = None
        preview_img = None

        for m in media_list:
            if m["type"] == "photo":
                preview_img = m["url"]
            elif m["type"] in ["video", "gif"]:
                preview_img = m["preview"]
                # pick the highest bitrate MP4
                for v in m["variants"]:
                    if v["content_type"] == "video/mp4":
                        hd_video = v["url"]

        return {
            "id": str(t["id"]),
            "text": t["text"],
            "url": t["url"],
            "author_name": t["author"]["name"],
            "author_handle": t["author"]["screen_name"],
            "stats": t["stats"],
            "image": preview_img,
            "video": hd_video
        }

    except Exception as e:
        print("FATAL ERROR:", e)
        return None


# ============================================================
# AUTO POSTER — fetches latest tweets from NFL timeline (FixTweet)
# ============================================================

def fetch_latest_from_user(username="NFL"):
    try:
        url = f"https://api.fxtwitter.com/user/{username}"
        print("FETCH LATEST:", url)

        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print("LATEST ERROR:", r.text)
            return []

        data = r.json()
        tweets = []

        for t in data.get("tweets", [])[:5]:
            tweets.append({
                "id": str(t["id"]),
                "text": t["text"],
                "url": t["url"],
                "stats": t.get("stats", {}),
                "media": t.get("media", [])
            })

        return tweets

    except:
        return []


# ============================================================
# SEND TWEET (AUTO)
# ============================================================

async def send_auto(tweet, channel, posted, force=False):

    if (not force) and tweet["id"] in posted:
        return

    image = None
    video = None

    for m in tweet["media"]:
        if m["type"] == "photo":
            image = m["url"]
        elif m["type"] in ["video", "gif"]:
            image = m["thumbnail_url"]
            for v in m.get("variants", []):
                if v["content_type"] == "video/mp4":
                    video = v["url"]

    embed = discord.Embed(description=tweet["text"], color=0x1DA1F2)
    embed.set_author(name="NFL (@NFL)", url=tweet["url"],
                     icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png")

    stats = tweet["stats"]
    embed.add_field(name="💬", value=stats.get("replies", 0))
    embed.add_field(name="🔁", value=stats.get("retweets", 0))
    embed.add_field(name="❤️", value=stats.get("likes", 0))
    embed.add_field(name="👁", value=stats.get("views", 0))

    if image:
        embed.set_image(url=image)

    await channel.send(embed=embed)

    if video:
        proxied = CDN_PROXY + quote(video, safe="")
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
        print("CHANNEL NOT FOUND")
        return

    posted = load_posted()
    tweets = fetch_latest_from_user("NFL")

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
    posted = load_posted()
    tweets = fetch_latest_from_user("NFL")

    for t in tweets:
        await send_auto(t, ch, posted)

    save_posted(posted)


# ============================================================
# !tweet — FULL FIXTWEET EMBED (video inside)
# ============================================================

TWEET_URL_REGEX = r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"

@bot.command()
async def tweet(ctx, url: str):
    match = re.search(TWEET_URL_REGEX, url)
    if not match:
        return await ctx.send("❌ Invalid link.")

    tweet_id = match.group(2)
    print("LOOKUP TWEET ID:", tweet_id)

    t = fetch_tweet_by_id(tweet_id)
    if not t:
        return await ctx.send("❌ Could not fetch tweet.")

    # Build embed server URL
    embed_url = (
        f"{EMBED_SERVER_URL}"
        f"?title=@{t['author_handle']}"
        f"&name={t['author_name']}"
        f"&handle={t['author_handle']}"
        f"&text={quote(t['text'])}"
        f"&likes={t['stats'].get('likes', 0)}"
        f"&retweets={t['stats'].get('retweets', 0)}"
        f"&replies={t['stats'].get('replies', 0)}"
        f"&views={t['stats'].get('views', 0)}"
    )

    if t["image"]:
        embed_url += "&image=" + quote(t["image"])

    if t["video"]:
        embed_url += "&video=" + quote(CDN_PROXY + quote(t["video"], safe=""))

    print("EMBED:", embed_url)
    await ctx.send(embed_url)


bot.run(DISCORD_TOKEN)
