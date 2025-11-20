# ZenRows Configuration Guide for Twitter Scraping

## ⚠️ CRITICAL: Why Your Bot Isn't Getting Tweets

Your ZenRows is returning only **159 bytes** of HTML instead of the full rendered page (20,000+ bytes). This means **JavaScript rendering is NOT working** in your ZenRows setup.

---

## ✅ Step-by-Step ZenRows Dashboard Configuration

### 1. **Verify Your API Key is Active**
- Go to https://app.zenrows.com
- Sign in to your account
- Copy your API key
- Paste it in your Replit Secrets as `ZENROWS_API_KEY`

---

### 2. **Enable JavaScript Rendering for Twitter Domain**

**THIS IS THE CRITICAL STEP!**

1. Go to **ZenRows Dashboard** → **Settings** (or Account Settings)
2. Look for **"Domains"** or **"Domain Configuration"**
3. Find or add **twitter.com** domain
4. Make sure these are ENABLED:
   - ✅ **JavaScript Rendering** (MANDATORY)
   - ✅ **Premium Proxy** (RECOMMENDED)
   - ✅ **Browser Emulation**
   - ✅ **Wait for Dynamic Content**

---

### 3. **Check Your ZenRows Tier & Credits**

The issue might be your account tier:

| Feature | Free Tier | Starter | Pro |
|---------|-----------|---------|-----|
| JS Rendering | ❌ NO | ✅ YES | ✅ YES |
| Premium Proxy | ❌ NO | Limited | ✅ YES |
| Twitter Support | ❌ | ⚠️ Limited | ✅ Full |

**If you're on Free tier → UPGRADE to Starter or Pro**

---

### 4. **Test ZenRows Directly**

Before relying on the bot, test ZenRows manually:

```python
from zenrows import ZenRowsClient

# Replace with YOUR API KEY
client = ZenRowsClient("YOUR_ZENROWS_API_KEY")

response = client.get(
    "https://twitter.com/nikhilraj__",
    params={
        "js_render": "true",
        "premium_proxy": "true",
    }
)

print(f"Status: {response.status_code}")
print(f"HTML Length: {len(response.text)}")
print(f"First 500 chars:\n{response.text[:500]}")
```

**Expected output**: `HTML Length: 20,000+` (not 159!)

If you get 159 bytes → JS rendering isn't enabled in your ZenRows account.

---

## 🔧 ZenRows Parameter Optimization

The bot code now uses the optimal 2024 parameters:

```python
params={
    # CORE REQUIREMENTS
    "js_render": "true",              # Renders JavaScript (MANDATORY)
    "premium_proxy": "true",          # Better anti-bot bypass
    "proxy_country": "us",            # Matches geo expectations
    
    # ADVANCED OPTIONS
    "json_response": "true",          # Captures XHR data
    "original_status": "true",        # Original HTTP status
    
    # PERFORMANCE
    "window_width": "1920",
    "window_height": "1080",
    "block_resources": "image",       # Skip images for speed
}
```

---

## 📋 Troubleshooting Checklist

- [ ] ZenRows API key is correct (check in Replit Secrets)
- [ ] JavaScript rendering is ENABLED in ZenRows dashboard for twitter.com
- [ ] Your ZenRows account tier supports JS rendering (Starter+)
- [ ] Premium proxy is enabled
- [ ] Test directly with the Python code above (confirm >2000 bytes)
- [ ] Check ZenRows credit balance (JavaScript rendering costs credits)
- [ ] Try the bot again and check logs for larger HTML size

---

## 💳 Credit Cost Breakdown

Each request to Twitter costs approximately:
- Base request: **1 credit**
- + JavaScript rendering: **+5 credits**
- + Premium proxy: **+10-25 credits**
- **TOTAL: ~16-31 credits per request**

If you're low on credits → Upgrade your plan.

---

## 🎯 Success Indicators

When ZenRows is configured correctly, you should see in the bot logs:
```
📤 Requesting via ZenRows...
📄 ZenRows received 25000+ bytes  ✅ (Not 159!)
🔍 Found X article tags
✅ Found X tweets
📬 Found X new tweet(s)
✅ Posted tweet to Discord
```

---

## 🚀 If It Still Doesn't Work

1. **Check ZenRows Status Page**: https://status.zenrows.com
2. **Contact ZenRows Support**: support@zenrows.com (mention Twitter scraping)
3. **Try an API Test Tool**: Use Postman or curl to test the API directly
4. **Verify Python SDK**: Run `pip install --upgrade zenrows`

---

## Alternative: Use Twitter's Free API Tier

If ZenRows continues to have issues, consider using **Twitter's official free API tier** instead:
- Free tier: 450 requests/month
- No JavaScript rendering needed (API returns structured JSON)
- More reliable than web scraping

Sign up at: https://developer.twitter.com/en/portal/dashboard

---

## Summary

**Your bot is ready.** You just need to:

1. **Go to ZenRows dashboard**
2. **Enable JavaScript rendering for twitter.com**
3. **Verify you have an account tier that supports it**
4. **Run the test Python code above**
5. **Confirm HTML is 20,000+ bytes (not 159)**

Once ZenRows returns proper HTML, the bot will automatically extract and post tweets! 🎉
