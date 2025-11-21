import sys
import json
import re
import requests

def fetch_tweets_direct(username):
    """Fetch tweets using direct API call with proper headers"""
    try:
        # X.com API endpoint - try to access public tweets
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        # Try direct web scrape first
        url = f'https://x.com/{username}'
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        
        if response.status_code == 200:
            # Extract tweet data from HTML using regex
            text = response.text
            
            # Look for tweet data in the page
            tweet_pattern = r'"rest_id":"(\d+)".*?"full_text":"([^"]*)"'
            matches = re.findall(tweet_pattern, text)
            
            tweets = []
            for tweet_id, tweet_text in matches[:20]:
                tweets.append({
                    'id': tweet_id,
                    'text': tweet_text[:500],
                    'url': f'https://x.com/{username}/status/{tweet_id}',
                    'timestamp': ''
                })
            
            if tweets:
                return tweets
        
        return []
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)
    
    username = sys.argv[1].lstrip('@')
    tweets = fetch_tweets_direct(username)
    print(json.dumps(tweets))
