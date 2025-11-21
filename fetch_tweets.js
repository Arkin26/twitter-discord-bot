import puppeteer from 'puppeteer';

async function main() {
  const username = process.argv[2];
  if (!username) {
    console.error('No username provided');
    process.exit(1);
  }

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--single-process'
      ]
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 1024 });
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0');

    const url = `https://x.com/${username}`;
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

    // Scroll to load tweets
    for (let i = 0; i < 5; i++) {
      await page.evaluate(() => window.scrollBy(0, window.innerHeight));
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    // Extract tweets
    const tweets = await page.evaluate(() => {
      const tweets = [];
      const articles = document.querySelectorAll('article');

      articles.forEach(article => {
        try {
          const link = article.querySelector('a[href*="/status/"]');
          if (!link) return;

          const href = link.getAttribute('href');
          const id = href.split('/status/')[1]?.split('?')[0];

          const textDiv = article.querySelector('[data-testid="tweetText"]');
          const text = textDiv?.innerText || '';

          const timeEl = article.querySelector('time');
          const timestamp = timeEl?.getAttribute('datetime') || new Date().toISOString();

          if (text && id) {
            tweets.push({
              id,
              text,
              url: `https://x.com${href}`,
              timestamp
            });
          }
        } catch (e) {}
      });

      return tweets;
    });

    await page.close();
    console.log(JSON.stringify(tweets.slice(0, 20)));
    process.exit(0);
  } catch (error) {
    console.error(JSON.stringify({ error: error.message }));
    process.exit(1);
  } finally {
    if (browser) await browser.close();
  }
}

main();
