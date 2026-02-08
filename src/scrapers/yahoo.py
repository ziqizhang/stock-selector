from src.scrapers.base import BaseScraper


class YahooFinanceScraper(BaseScraper):
    BASE_URL = "https://finance.yahoo.com"

    async def scrape(self, symbol: str) -> dict:
        fundamentals = await self._scrape_fundamentals(symbol)
        analyst = await self._scrape_analyst(symbol)
        return {"fundamentals": fundamentals, "analyst": analyst}

    async def _scrape_fundamentals(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}/quote/{symbol}/")
        soup = self.parse_html(html)
        data = {}
        for row in soup.select('[data-testid="quote-statistics"] tr'):
            cells = row.find_all("td")
            if len(cells) == 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                data[label] = value
        return data

    async def _scrape_analyst(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}/quote/{symbol}/analysis/")
        soup = self.parse_html(html)
        data = {}
        tables = soup.find_all("table")
        for table in tables:
            header = table.find("thead")
            if header:
                title = header.get_text(strip=True)
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if cells:
                        rows.append(cells)
                data[title] = rows
        return data
