import logging
import re

from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class InvestegateScraper(BaseScraper):
    """Scrape UK director dealings from Investegate."""

    BASE_URL = "https://www.investegate.co.uk"
    LISTING_URL = f"{BASE_URL}/Index.aspx?CategoryId=3"  # Directors' Dealings category

    async def scrape(self, symbol: str) -> dict:
        # Investegate uses bare symbols (e.g. VOD not VOD.L)
        bare_symbol = symbol.replace(".L", "")

        html = await self.fetch(self.LISTING_URL)
        soup = self.parse_html(html)

        matching_links = []
        for row in soup.select("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            # The listing table has columns like: Date, Source, Headline
            # Company symbols/names appear in the source or headline cells
            row_text = row.get_text(" ", strip=True).upper()
            if bare_symbol.upper() in row_text:
                link = row.find("a", href=True)
                if link and "/Article.aspx" in link["href"]:
                    href = link["href"]
                    if not href.startswith("http"):
                        href = self.BASE_URL + "/" + href.lstrip("/")
                    matching_links.append({
                        "url": href,
                        "headline": link.get_text(strip=True),
                        "date": cells[0].get_text(strip=True) if cells else "",
                    })

        # Fetch detail pages for top 5 matching announcements
        trades = []
        for item in matching_links[:5]:
            trade = await self._parse_detail(item)
            if trade:
                trades.append(trade)

        return {"insider_trades": trades}

    async def _parse_detail(self, item: dict) -> dict | None:
        """Fetch an individual RNS announcement and try to parse trade details."""
        try:
            html = await self.fetch(item["url"])
        except Exception as e:
            logger.warning("Failed to fetch Investegate detail page %s: %s", item["url"], e)
            return {
                "filing_date": item.get("date", ""),
                "trade_date": item.get("date", ""),
                "insider_name": "",
                "title": "",
                "trade_type": "",
                "price": "",
                "qty": "",
                "value": "",
                "headline": item.get("headline", ""),
            }

        soup = self.parse_html(html)
        body = soup.get_text("\n", strip=True)

        # Try to extract structured fields from the RNS text
        director = self._extract_field(body, r"(?:Director|PDMR)\s*:\s*([^\n]+)")
        trade_type = self._extract_field(body, r"(?:Nature of transaction|Type)[:\s]+(Purchase|Sale|Buy|Sell|Award)")
        shares = self._extract_field(body, r"(?:Number of (?:shares|securities)|Shares)[:\s]+([\d,]+)")
        price = self._extract_field(body, r"(?:Price per share|Price)[:\s]+([£\d.,]+)")
        value = self._extract_field(body, r"(?:Aggregate value|Value|Total)[:\s]+([£\d.,]+)")

        return {
            "filing_date": item.get("date", ""),
            "trade_date": item.get("date", ""),
            "insider_name": director or "",
            "title": "",
            "trade_type": trade_type or "",
            "price": price or "",
            "qty": shares or "",
            "value": value or "",
            "headline": item.get("headline", ""),
        }

    @staticmethod
    def _extract_field(text: str, pattern: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None
