from src.scrapers.base import BaseScraper

SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}


class SectorScraper(BaseScraper):
    async def scrape(self, symbol: str, sector: str | None = None) -> dict:
        html = await self.fetch("https://finviz.com/groups.ashx?g=sector&v=110&o=-perf1w")
        soup = self.parse_html(html)
        sector_data = []
        table = soup.find("table", class_="table-light")
        if table:
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 3:
                    sector_data.append({
                        "name": cells[1],
                        "perf_week": cells[2] if len(cells) > 2 else "",
                        "perf_month": cells[3] if len(cells) > 3 else "",
                        "perf_ytd": cells[6] if len(cells) > 6 else "",
                    })

        sector_name = sector or "market"
        news_html = await self.fetch(
            f"https://www.google.com/search?q={sector_name}+sector+stock+market+news&tbm=nws&num=5"
        )
        news_soup = self.parse_html(news_html)
        sector_news = []
        for item in news_soup.select("div.SoaBEf"):
            title_el = item.select_one("div.MBeuO")
            if title_el:
                sector_news.append({"title": title_el.get_text(strip=True)})

        return {
            "sector_performance": sector_data,
            "sector_news": sector_news,
            "ticker_sector": sector,
            "sector_etf": SECTOR_ETFS.get(sector, "SPY") if sector else "SPY",
        }
