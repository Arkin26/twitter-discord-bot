import express from "express";
import cors from "cors";
import fetch from "node-fetch";

const app = express();
app.use(cors());

const PORT = process.env.PORT || 3000;
const API_KEY = process.env.ZENROWS_API_KEY;

// Tweets fetcher using ZenRows
async function fetchTweets(username) {
  const url = `https://x.com/${username}`;

  const apiUrl = `https://api.zenrows.com/v1/?apikey=${API_KEY}&url=${encodeURIComponent(
    url
  )}&js_render=true&autoparse=true`;

  const response = await fetch(apiUrl);
  const data = await response.text();

  return data; // raw HTML → we parse next
}

import * as cheerio from "cheerio";

// Parse tweets HTML into JSON
function parseTweets(html) {
  const $ = cheerio.load(html);
  const tweets = [];

  $("article").each((i, el) => {
    const idMatch = $(el).find("a[href*='/status/']").attr("href")?.match(/status\/(\d+)/);
    if (!idMatch) return;

    const id = idMatch[1];
    const text = $(el).find("div[data-testid='tweetText']").text().trim();
    const date = $(el).find("time").attr("datetime") || null;

    const media = [];
    $(el)
      .find("img")
      .each((_, img) => media.push($(img).attr("src")));
    $(el)
      .find("video")
      .each((_, vid) => media.push($(vid).attr("src")));

    tweets.push({
      id,
      text,
      date,
      url: "https://x.com" + $(el).find("a[href*='/status/']").attr("href"),
      media,
    });
  });

  return tweets.slice(0, 10); // limit to 10 tweets
}

// API endpoint
app.get("/tweets", async (req, res) => {
  const user = req.query.user;
  if (!user) return res.status(400).json({ error: "Missing ?user=" });

  try {
    const html = await fetchTweets(user);
    const tweets = parseTweets(html);
    res.json({ tweets });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to scrape tweets" });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`🐦 Twitter API backend running on ${PORT}`);
});
