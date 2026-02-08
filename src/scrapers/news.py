from src.scrapers.base import BaseScraper


class NewsScraper(BaseScraper):
    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(
            f"https://www.google.com/search?q={symbol}+stock+news&tbm=nws&num=10"
        )
        soup = self.parse_html(html)
        articles = []
        for item in soup.select("div.SoaBEf"):
            title_el = item.select_one("div.MBeuO")
            source_el = item.select_one("div.OSrXXb span")
            snippet_el = item.select_one("div.GI74Re")
            if title_el:
                articles.append({
                    "title": title_el.get_text(strip=True),
                    "source": source_el.get_text(strip=True) if source_el else "",
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
        return {"news_articles": articles}
