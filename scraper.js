import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COOKIES_FILE = path.join(__dirname, 'cookies.json');

let browser = null;

async function initBrowser() {
  if (browser) return browser;
  
  // Use system chromium if available, fallback to puppeteer's bundled version
  let executablePath = undefined;
  try {
    const { execSync } = await import('child_process');
    executablePath = execSync('which chromium').toString().trim();
  } catch {
    console.log('Using Puppeteer bundled Chromium');
  }
  
  browser = await puppeteer.launch({
    headless: 'new',
    executablePath: executablePath || undefined,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--single-process',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-web-resources',
      '--disable-extensions'
    ]
  });
  
  return browser;
}

async function loadCookies(page) {
  try {
    if (fs.existsSync(COOKIES_FILE)) {
      const cookies = JSON.parse(fs.readFileSync(COOKIES_FILE, 'utf8'));
      if (cookies.length > 0) {
        await page.setCookie(...cookies);
        console.log('✅ Cookies loaded');
        return true;
      }
    }
  } catch (error) {
    console.log('⚠️ No cookies available - using public scraping');
  }
  return false;
}

async function extractTweets(page) {
  return await page.evaluate(() => {
    const tweets = [];
    const tweetElements = document.querySelectorAll('article');
    
    tweetElements.forEach((article) => {
      try {
        // Get tweet link
        const link = article.querySelector('a[href*="/status/"]');
        if (!link) return;
        
        const href = link.getAttribute('href');
        const tweetId = href.split('/status/')[1]?.split('?')[0];
        
        // Get tweet text
        const textDiv = article.querySelector('[data-testid="tweetText"]');
        const text = textDiv?.innerText || '';
        
        // Get timestamp
        const timeElement = article.querySelector('time');
        const timestamp = timeElement?.getAttribute('datetime') || new Date().toISOString();
        
        if (text && tweetId) {
          tweets.push({
            id: tweetId,
            text: text,
            url: `https://x.com${href}`,
            timestamp: timestamp
          });
        }
      } catch (error) {
        // Skip errored tweets
      }
    });
    
    return tweets;
  });
}

export async function fetchTweets(username) {
  console.log(`🔍 Fetching tweets from @${username}...`);
  
  const browser = await initBrowser();
  const page = await browser.newPage();
  
  try {
    // Set viewport
    await page.setViewport({ width: 1280, height: 1024 });
    
    // Set user agent
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    
    // Load cookies if available
    await loadCookies(page);
    
    // Navigate to profile
    const url = `https://x.com/${username}`;
    console.log(`🌐 Loading ${url}`);
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    
    // Scroll to load more tweets
    console.log('⏬ Scrolling to load tweets...');
    let previousHeight = 0;
    let scrollCount = 0;
    const maxScrolls = 5;
    
    while (scrollCount < maxScrolls) {
      const currentHeight = await page.evaluate(() => document.body.scrollHeight);
      
      if (currentHeight === previousHeight) {
        break;
      }
      
      previousHeight = currentHeight;
      await page.evaluate(() => {
        window.scrollBy(0, window.innerHeight);
      });
      
      await new Promise(resolve => setTimeout(resolve, 1000));
      scrollCount++;
    }
    
    // Extract tweets
    const tweets = await extractTweets(page);
    console.log(`✅ Extracted ${tweets.length} tweets`);
    
    // Return at least the tweets we found (even if fewer than 10)
    return tweets.slice(0, 20);
    
  } catch (error) {
    console.error('❌ Scraping error:', error.message);
    throw new Error(`Failed to scrape @${username}: ${error.message}`);
  } finally {
    await page.close();
  }
}
