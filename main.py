import threading
import os
from flask import Flask, render_template_string, request
import discord
from discord.ext import commands, tasks
import requests
import json
from urllib.parse import quote

# -----------------------------
# ENV VARIABLES
# -----------------------------

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", 0))
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# -----------------------------
# FLASK EMBED SERVER
# -----------------------------

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta property="og:title" content="{{ title }}">
<meta property="og:description" content="{{ text }}">
{% if image_url %}
<meta property="og:image" content="{{ image_url }}">
{% endif %}
<title>{{ title }}</title>
</head>
<body style="background:#0f1419;color:white;font-family:sans-serif;padding:20px;">
<h2>{{ name }} (@{{ handle }})</h2>
<p style="white-space:pre-wrap;">{{ text }}</p>

{% if video_url %}
<video controls autoplay muted style="width:100%;border-radius:12px;">
  <source src="{{ video_url }}" type="video/mp4">
</video>
{% elif image_url %}
<img src="{{ image_url }}" style="width:100%;border-radius:12px;" />
{% endif %}

</body>
</html>
"""

@app.route("/")
def embed_page():
    return render_template_string(
        HTML_TEMPLATE,
        title=request.args.get("title", "Tweet"),
        text=request.args.get("text", ""),
        name=request.args.get("name", "User"),
        handle=request.args.get("handle", "user"),
        image_url=request.args.get("image"),
        video_url=request.args.get("video")
    )

# -----------------------------
# DISCORD BOT
# -----------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

POSTED_FILE = "posted.json"

def load_posted():
    if os.path.exists(POSTED_FILE):
        return json.load(open(POSTED_FILE))
    return {}

def save_posted(data):
    json.dump(data, open(POSTED_FILE, "w"))

def get_tweets(username="NFL"):
    if not TWITTER_BEARER_TOKEN:
        return []

    url = f"https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    params = {
        "query": f"from:{username}",
        "expansions": "attachments.media_keys",
        "media.fields": "url,preview_image_url,variants,type",
        "tweet.fields": "id,text,public_metrics"
    }

    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        print("Twitter error:", r.text)
        return []

    data = r.json()
    media_map = {}

    if "includes" in data and "media" in data["includes"]:
        for m in data["includes"]["media"]:
            media_map[m["media_key"]] = m

    tweets = []
    for t in data.get("data", []):
        media_list = []
        keys = t.get("attachments", {}).get("media_keys", [])
        for k in keys:
            m = media_map.get(k)
            if not m: continue
            video = None
            if m["type"] in ["video", "animated_gif"]:
                for v in m.get("variants", []):
                    if v.get("content_type") == "video/mp4":
                        video = v["url"]
                        break
            media_list.append({
                "type": m["type"],
                "image": m.get("url"),
                "preview": m.get("preview_image_url"),
                "video": video
            })
        tweets.append({
            "id": t["id"],
            "text": t["text"],
            "metrics": t["public_metrics"],
            "media": media_list,
            "url": f"https://x.com/{username}/status/{t['id']}"
        })

    return tweets

async def post_tweet(tweet, channel, posted):
    media = tweet["media"][0] if tweet["media"] else None
    img = media["image"] if media else None
    vid = media["video"] if media else None

    embed_url = (
        f"{os.getenv('APP_URL')}"
        f"?title=@NFL&name=NFL&handle=NFL"
        f"&text={quote(tweet['text'])}"
    )
    if img: embed_url += f"&image={quote(img)}"
    if vid: embed_url += f"&video={quote(vid)}"

    embed = discord.Embed(description=f"[Tweet Link]({tweet['url']})")
    await channel.send(embed=embed, content=embed_url)

    posted[tweet["id"]] = True
    save_posted(posted)

@tasks.loop(minutes=2)
async def tweet_loop():
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    posted = load_posted()

    tweets = get_tweets("NFL")
    if not tweets:
        print("No tweets")
        return

    for t in tweets[:2]:
        if t["id"] not in posted:
            await post_tweet(t, channel, posted)

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    if not tweet_loop.is_running():
        tweet_loop.start()

# -----------------------------
# RUN BOTH SYSTEMS TOGETHER
# -----------------------------

def start_discord():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    threading.Thread(target=start_discord).start()
    app.run(host="0.0.0.0", port=5000)
