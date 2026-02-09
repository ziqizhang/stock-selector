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
        
        # Look for all announcement links and filter by symbol
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            text = str(link.get_text(strip=True)).upper()
            
            # Check if this is an announcement link (updated pattern)
            href_str = str(href)
            if "/announcement/" in href_str:
                # Check if symbol appears in text or URL
                if bare_symbol in text or bare_symbol in href_str.upper():
                    # Initialize date for this link
                    date = ""
                    # Get the parent container to find date info
                    parent = link.find_parent()
                    # Try to find date in parent or nearby elements
                    for elem in [parent, link.find_previous(), link.find_next()]:
                        if elem:
                            elem_text = elem.get_text(strip=True)
                            # Look for date patterns (YYYY-MM-DD, DD/MM/YYYY, etc.)
                            date_match = re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2}', elem_text)
                            if date_match:
                                date = date_match.group()
                                break
                    
                    href_str = str(href)
                    if not str(href_str).startswith("http"):
                        full_href = self.BASE_URL + str(href_str).lstrip("/")
                    else:
                        full_href = href_str
                    
                    matching_links.append({
                        "url": full_href,
                        "headline": link.get_text(strip=True),
                        "date": date,
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
