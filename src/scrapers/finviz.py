from src.scrapers.base import BaseScraper


class FinvizScraper(BaseScraper):
    BASE_URL = "https://finviz.com/quote.ashx"

    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}?t={symbol}&p=d")
        soup = self.parse_html(html)
        technicals = self._parse_technicals(soup)
        news = self._parse_news(soup)
        return {"technicals": technicals, "news": news}

    def _parse_technicals(self, soup) -> dict:
        data = {}
        table = soup.find("table", class_="snapshot-table2")
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                for i in range(0, len(cells) - 1, 2):
                    label = cells[i].get_text(strip=True)
                    value = cells[i + 1].get_text(strip=True)
                    data[label] = value
        return data

    def _parse_news(self, soup) -> list[dict]:
        news = []
        news_table = soup.find("table", id="news-table")
        if news_table:
            for row in news_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    timestamp = cells[0].get_text(strip=True)
                    link = cells[1].find("a")
                    if link:
                        news.append({
                            "timestamp": timestamp,
                            "title": link.get_text(strip=True),
                            "url": link.get("href", ""),
                        })
        return news
