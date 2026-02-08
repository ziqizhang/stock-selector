from src.scrapers.base import BaseScraper

# Keys from the Finviz snapshot table grouped by category
FUNDAMENTAL_KEYS = {
    "P/E", "Forward P/E", "PEG", "P/S", "P/B", "P/C", "P/FCF",
    "EPS (ttm)", "EPS next Y", "EPS next Q", "EPS this Y", "EPS next 5Y",
    "EPS past 3/5Y", "EPS Q/Q", "EPS Y/Y TTM", "EPS/Sales Surpr.",
    "Sales", "Sales Q/Q", "Sales Y/Y TTM", "Sales past 3/5Y",
    "Income", "Gross Margin", "Oper. Margin", "Profit Margin",
    "ROA", "ROE", "ROIC", "Current Ratio", "Quick Ratio",
    "Debt/Eq", "LT Debt/Eq", "Market Cap", "Enterprise Value",
    "EV/EBITDA", "EV/Sales", "Book/sh", "Cash/sh", "Dividend TTM",
    "Dividend Est.", "Payout", "Employees",
}

ANALYST_KEYS = {
    "Target Price", "Recom", "Price", "Insider Own", "Inst Own",
    "Insider Trans", "Inst Trans", "Short Float", "Short Ratio",
    "Short Interest",
}

TECHNICAL_KEYS = {
    "RSI (14)", "SMA20", "SMA50", "SMA200", "ATR (14)",
    "Volatility", "Beta", "52W High", "52W Low", "Price",
    "Prev Close", "Change", "Volume", "Avg Volume", "Rel Volume",
    "Perf Week", "Perf Month", "Perf Quarter", "Perf Half Y",
    "Perf Year", "Perf YTD",
}


class FinvizScraper(BaseScraper):
    BASE_URL = "https://finviz.com/quote.ashx"

    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}?t={symbol}&p=d")
        soup = self.parse_html(html)
        all_data = self._parse_snapshot(soup)
        news = self._parse_news(soup)
        return {
            "all_data": all_data,
            "fundamentals": {k: v for k, v in all_data.items() if k in FUNDAMENTAL_KEYS},
            "analyst": {k: v for k, v in all_data.items() if k in ANALYST_KEYS},
            "technicals": {k: v for k, v in all_data.items() if k in TECHNICAL_KEYS},
            "news": news,
        }

    def _parse_snapshot(self, soup) -> dict:
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
