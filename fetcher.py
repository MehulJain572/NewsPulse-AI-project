import os
import requests
import feedparser
from dotenv import load_dotenv

load_dotenv()

# API Keys from .env
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Target handles for Twitter RSS
TARGET_HANDLES = ["ETMarkets", "moneycontrolcom", "DeItaone", "HindenburgRes", "FinMinIndia"]

def fetch_twitter_rss():
    """getting twitter updates from Google News RSS (No Login)"""
    print("[LOG] Fetching Twitter updates via RSS...")
    headlines = []
    for handle in TARGET_HANDLES:
        try:
            url = f"https://news.google.com/rss/search?q={handle}+Twitter"
            feed = feedparser.parse(url)
            if feed.entries:
                headlines.append(f"X-Source (@{handle}): {feed.entries[0].title}")
        except Exception as e:
            print(f"[!] Error fetching Twitter RSS for @{handle}: {e}")
    return headlines

def fetch_finnhub_news():
    print("[LOG] Fetching Finnhub news...")
    headlines = []
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Top 5 headlines 
            for item in data[:5]:
                headlines.append(f"Finnhub: {item['headline']}")
        else:
            print(f"[!] Finnhub API Error: Status {response.status_code}")
    except Exception as e:
        print(f"[!] Finnhub Connection Failed: {e}")
    return headlines

def fetch_newsapi_data():
    print("[LOG] Fetching NewsAPI data...")
    headlines = []
    # Sensex & nifty related news
    url = f"https://newsapi.org/v2/everything?q=Sensex+OR+Nifty+OR+Adani&language=en&sortBy=publishedAt&pageSize=7&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            articles = response.json().get('articles', [])
            for art in articles:
                headlines.append(f"NewsAPI: {art['title']}")
        else:
            print(f"[!] NewsAPI Error: Status {response.status_code}")
    except Exception as e:
        print(f"[!] NewsAPI Connection Failed: {e}")
    return headlines

def get_all_headlines():
    t_news = fetch_twitter_rss()
    f_news = fetch_finnhub_news()
    n_news = fetch_newsapi_data()
    
    print(f"\n--- DATA SUMMARY ---")
    print(f"Twitter RSS: {len(t_news)} captured")
    print(f"Finnhub: {len(f_news)} captured")
    print(f"NewsAPI: {len(n_news)} captured")
    
    return t_news + f_news + n_news

if __name__ == "__main__":
    all_data = get_all_headlines()
    
    print("\n" + "="*60)
    print(f"TOTAL HEADLINES COLLECTED: {len(all_data)}")
    print("="*60)
    for i, h in enumerate(all_data, 1):
        print(f"{i}. {h}")
    print("="*60)