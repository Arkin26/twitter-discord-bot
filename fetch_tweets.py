import sys
import json
import requests
import os
from pathlib import Path

# Cache file for user IDs
USER_CACHE_FILE = 'user_id_cache.json'

def load_user_cache():
    if Path(USER_CACHE_FILE).exists():
        try:
            return json.load(open(USER_CACHE_FILE))
        except:
            return {}
    return {}

def save_user_cache(cache):
    json.dump(cache, open(USER_CACHE_FILE, 'w'), indent=2)

def fetch_tweets_api(username):
    """Fetch tweets using Twitter API v2"""
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    
    if not bearer_token:
        return []
    
    try:
        cache = load_user_cache()
        headers = {'Authorization': f'Bearer {bearer_token}'}
        
        # Get user ID (with caching)
        if username not in cache:
            user_url = f'https://api.twitter.com/2/users/by/username/{username}'
            user_response = requests.get(user_url, headers=headers, timeout=10)
            
            if user_response.status_code != 200:
                return []
            
            user_id = user_response.json()['data']['id']
            cache[username] = user_id
            save_user_cache(cache)
        else:
            user_id = cache[username]
        
        # Get recent tweets
        tweets_url = f'https://api.twitter.com/2/users/{user_id}/tweets'
        params = {
            'max_results': 20,
            'tweet.fields': 'created_at'
        }
        
        tweets_response = requests.get(tweets_url, headers=headers, params=params, timeout=10)
        
        if tweets_response.status_code != 200:
            return []
        
        data = tweets_response.json()
        tweets = []
        
        if 'data' in data:
            for tweet in data['data']:
                tweets.append({
                    'id': tweet['id'],
                    'text': tweet['text'],
                    'url': f'https://x.com/{username}/status/{tweet["id"]}',
                    'timestamp': tweet.get('created_at', '')
                })
        
        return tweets
    except:
        return []

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)
    
    username = sys.argv[1].lstrip('@')
    tweets = fetch_tweets_api(username)
    print(json.dumps(tweets))
