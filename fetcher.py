import hashlib
import json
import os
import xml.etree.ElementTree as ET
from urllib import request
from urllib.parse import quote_plus

from env_utils import load_local_env

load_local_env()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

TARGET_HANDLES = ["ETMarkets", "moneycontrolcom", "DeItaone", "HindenburgRes", "FinMinIndia"]


def _build_news_item(source, headline, url="", published_at=""):
    normalized = " ".join((headline or "").lower().split())
    fingerprint = hashlib.sha256(f"{source}|{normalized}".encode("utf-8")).hexdigest()
    return {
        "source": source,
        "headline": headline.strip(),
        "url": url,
        "published_at": published_at,
        "fingerprint": fingerprint,
    }


def fetch_twitter_rss():
    print("[LOG] Fetching X/Twitter watchlist via Google News RSS...")
    headlines = []

    for handle in TARGET_HANDLES:
        try:
            query = quote_plus(f"{handle} Twitter")
            url = f"https://news.google.com/rss/search?q={query}"
            with request.urlopen(url, timeout=10) as response:
                root = ET.fromstring(response.read())
            items = root.findall(".//item")

            for entry in items[:1]:
                headlines.append(
                    _build_news_item(
                        source=f"x_rss:{handle}",
                        headline=(entry.findtext("title") or "").strip(),
                        url=(entry.findtext("link") or "").strip(),
                        published_at=(entry.findtext("pubDate") or "").strip(),
                    )
                )
        except Exception as exc:
            print(f"[WARN] RSS fetch failed for @{handle}: {exc}")

    return headlines


def fetch_finnhub_news():
    print("[LOG] Fetching Finnhub headlines...")
    headlines = []

    if not FINNHUB_API_KEY:
        print("[WARN] FINNHUB_API_KEY missing.")
        return headlines

    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"

    try:
        with request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for item in payload[:5]:
            headlines.append(
                _build_news_item(
                    source="finnhub",
                    headline=item.get("headline", ""),
                    url=item.get("url", ""),
                    published_at=str(item.get("datetime", "")),
                )
            )
    except Exception as exc:
        print(f"[WARN] Finnhub fetch failed: {exc}")

    return headlines


def fetch_newsapi_data():
    print("[LOG] Fetching NewsAPI headlines...")
    headlines = []

    if not NEWS_API_KEY:
        print("[WARN] NEWS_API_KEY missing.")
        return headlines

    url = (
        "https://newsapi.org/v2/everything?"
        f"q={quote_plus('Sensex OR Nifty OR Adani OR Tata OR Reliance')}"
        "&language=en&sortBy=publishedAt&pageSize=7"
        f"&apiKey={NEWS_API_KEY}"
    )

    try:
        with request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))

        for article in payload.get("articles", []):
            headlines.append(
                _build_news_item(
                    source="newsapi",
                    headline=article.get("title", ""),
                    url=article.get("url", ""),
                    published_at=article.get("publishedAt", ""),
                )
            )
    except Exception as exc:
        print(f"[WARN] NewsAPI fetch failed: {exc}")

    return headlines


def get_all_headlines():
    items = fetch_twitter_rss() + fetch_finnhub_news() + fetch_newsapi_data()
    deduped = {}

    for item in items:
        if item["headline"]:
            deduped[item["fingerprint"]] = item

    print("\n--- DATA SUMMARY ---")
    print(f"Total fetched: {len(items)}")
    print(f"Unique headlines: {len(deduped)}")

    return list(deduped.values())


if __name__ == "__main__":
    for idx, item in enumerate(get_all_headlines(), 1):
        print(f"{idx}. [{item['source']}] {item['headline']}")
