from src.scrapers.base import BaseScraper


class OpenInsiderScraper(BaseScraper):
    BASE_URL = "http://openinsider.com/screener"

    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(
            f"{self.BASE_URL}?s={symbol}&o=&pl=&ph=&st=0&lt=1&lk=&fs=&fr=&fl=&per=&rec=&na=&fdlyl=&fdlyh=&lu=&gh=&gl=&sa=&slt=&sct=&isceo=1&iscfo=1&isd=1&ipp=50&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=25&page=1"
        )
        soup = self.parse_html(html)
        return {"insider_trades": self._parse_trades(soup)}

    def _parse_trades(self, soup) -> list[dict]:
        trades = []
        table = soup.find("table", class_="tinytable")
        if not table:
            return trades
        rows = table.find_all("tr")[1:]
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) >= 12:
                trades.append({
                    "filing_date": cells[1],
                    "trade_date": cells[2],
                    "ticker": cells[3],
                    "insider_name": cells[4],
                    "title": cells[5],
                    "trade_type": cells[6],
                    "price": cells[7],
                    "qty": cells[8],
                    "owned": cells[9],
                    "change_pct": cells[10],
                    "value": cells[11],
                })
        return trades
