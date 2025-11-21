import sys
import json
import snscrape.modules.twitter as sntwitter

def fetch_tweets(username):
    """Fetch tweets using snscrape"""
    try:
        tweets = []
        for i, tweet in enumerate(sntwitter.TwitterProfileScraper(username).get_items()):
            if i >= 20:
                break
            tweets.append({
                'id': str(tweet.id),
                'text': tweet.content,
                'url': f'https://x.com/{username}/status/{tweet.id}',
                'timestamp': tweet.date.isoformat()
            })
        return tweets
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return []

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)
    
    username = sys.argv[1].lstrip('@')
    tweets = fetch_tweets(username)
    print(json.dumps(tweets))
