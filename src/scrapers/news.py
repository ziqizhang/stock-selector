import feedparser

from src.scrapers.base import BaseScraper


class NewsScraper(BaseScraper):
    async def scrape(self, symbol: str) -> dict:
        url = f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"
        content = await self.fetch(url)
        feed = feedparser.parse(content)
        articles = []
        for entry in feed.entries:
            source = entry.get("source", {})
            articles.append({
                "title": entry.get("title", ""),
                "source": source.get("title", "") if isinstance(source, dict) else "",
                "snippet": entry.get("summary", ""),
            })
        return {"news_articles": articles}
