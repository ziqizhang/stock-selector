import hashlib
import json
import logging
import os
from typing import AsyncGenerator
from src.scrapers.provider import DataProvider
from src.scrapers.finviz import FinvizScraper
from src.scrapers.finviz_provider import FinvizDataProvider
from src.scrapers.yfinance_provider import YFinanceProvider
from src.scrapers.openinsider import OpenInsiderScraper
from src.scrapers.investegate import InvestegateScraper
from src.scrapers.news import NewsScraper
from src.scrapers.sector import SectorScraper
from src.analysis.llm_base import LLMProvider
from src.analysis.claude import ClaudeCLI
from src.analysis.codex import CodexCLI
from src.analysis.opencode import OpencodeCLI
from src.analysis import prompts
from src.analysis.scoring import weighted_score, score_to_recommendation
from src.db import Database
from src.models import RefreshProgress

logger = logging.getLogger(__name__)

VALID_CONFIDENCE_LEVELS = {"low", "medium", "high"}


def _validate_signal_result(result: dict) -> dict:
    """Clamp score to [-10, +10] and validate confidence level."""
    validated = dict(result)

    raw_score = validated.get("score", 0)
    clamped_score = max(-10, min(10, raw_score))
    if clamped_score != raw_score:
        logger.warning(
            "Score %s out of range [-10, +10], clamped to %s",
            raw_score, clamped_score,
        )
    validated["score"] = clamped_score

    raw_confidence = validated.get("confidence", "low")
    if raw_confidence not in VALID_CONFIDENCE_LEVELS:
        logger.warning(
            "Invalid confidence '%s', defaulting to 'low'", raw_confidence,
        )
        raw_confidence = "low"
    validated["confidence"] = raw_confidence

    return validated


def create_llm_provider(backend: str) -> LLMProvider:
    """Create an LLM provider instance by backend name."""
    if backend == "claude":
        return ClaudeCLI()
    elif backend == "codex":
        return CodexCLI()
    elif backend == "opencode":
        return OpencodeCLI()
    else:
        raise ValueError(f"STOCK_SELECTOR_LLM must be 'codex', 'claude', or 'opencode', got '{backend}'")


class AnalysisEngine:
    def __init__(self, db: Database, data_provider: DataProvider | None = None):
        self.db = db
        backend = os.environ.get("STOCK_SELECTOR_LLM", "codex").lower()
        self.llm: LLMProvider = create_llm_provider(backend)
        cache_get = db.get_cached_scrape
        cache_save = db.save_scrape_cache
        if data_provider is not None:
            self.data_provider = data_provider
        else:
            source = os.environ.get("STOCK_SELECTOR_DATA_SOURCE", "yfinance").lower()
            if source == "yfinance":
                self.data_provider = YFinanceProvider()
            elif source == "finviz":
                self.data_provider = FinvizDataProvider(
                    FinvizScraper(cache_get=cache_get, cache_save=cache_save)
                )
            else:
                raise ValueError(
                    f"STOCK_SELECTOR_DATA_SOURCE must be 'yfinance' or 'finviz', got '{source}'"
                )
        self.openinsider = OpenInsiderScraper(cache_get=cache_get, cache_save=cache_save)
        self.investegate = InvestegateScraper(cache_get=cache_get, cache_save=cache_save)
        self.news = NewsScraper(cache_get=cache_get, cache_save=cache_save)
        self.sector = SectorScraper(cache_get=cache_get, cache_save=cache_save)

    async def analyze_ticker(self, symbol: str) -> AsyncGenerator[RefreshProgress, None]:
        """Run full analysis for a ticker, yielding progress updates."""
        ticker = await self.db.get_ticker(symbol)
        if not ticker:
            yield RefreshProgress(symbol=symbol, step="error", done=True)
            return

        sector = ticker.get("sector")
        market = ticker.get("market", "US")
        all_scraped = {}
        signal_results = {}

        # Resolve symbol via yfinance if using that provider and not yet resolved
        resolved = ticker.get("resolved_symbol") or symbol
        if isinstance(self.data_provider, YFinanceProvider) and not ticker.get("resolved_symbol"):
            try:
                resolved, market = self.data_provider.resolve_symbol(symbol, preferred_market=market)
                await self.db.update_ticker_resolution(symbol, resolved, market)
            except ValueError:
                logger.warning(f"Could not resolve symbol {symbol}, using as-is")
                resolved = symbol

        # 1. Fetch primary data (fundamentals + technicals + analyst + news)
        yield RefreshProgress(symbol=symbol, step="Fetching market data...", category="fundamentals")
        try:
            fundamentals = await self.data_provider.get_fundamentals(resolved)
            technicals = await self.data_provider.get_technicals(resolved)
            analyst = await self.data_provider.get_analyst_data(resolved)
            provider_news = await self.data_provider.get_news(resolved)
        except Exception as e:
            logger.error(f"Data provider scrape failed for {symbol}: {e}")
            fundamentals = {}
            technicals = {}
            analyst = {}
            provider_news = []
        finviz_data = {
            "fundamentals": fundamentals,
            "analyst": analyst,
            "technicals": technicals,
            "news": provider_news,
        }
        all_scraped["primary"] = finviz_data

        # 2. Scrape insider activity (market-dependent)
        yield RefreshProgress(symbol=symbol, step="Scraping insider data...", category="insider_activity")
        try:
            if market == "UK":
                insider_data = await self.investegate.scrape(symbol)
            else:
                insider_data = await self.openinsider.scrape(symbol)
            all_scraped["openinsider"] = insider_data
        except Exception as e:
            logger.error(f"Insider scrape failed for {symbol}: {e}")
            insider_data = {"insider_trades": []}
            all_scraped["openinsider"] = insider_data

        # 3. Scrape news
        yield RefreshProgress(symbol=symbol, step="Scraping news...", category="sentiment")
        try:
            news_data = await self.news.scrape(symbol)
            all_scraped["news"] = news_data
        except Exception as e:
            logger.error(f"News scrape failed for {symbol}: {e}")
            news_data = {"news_articles": []}
            all_scraped["news"] = news_data

        # 4. Scrape sector context
        yield RefreshProgress(symbol=symbol, step="Scraping sector data...", category="sector_context")
        try:
            sector_data = await self.sector.scrape(symbol, sector, market=market)
            all_scraped["sector"] = sector_data
        except Exception as e:
            logger.error(f"Sector scrape failed for {symbol}: {e}")
            sector_data = {"sector_performance": [], "sector_news": []}
            all_scraped["sector"] = sector_data

        # 5. LLM Analysis — one per signal category
        categories = [
            ("fundamentals", prompts.fundamentals_prompt, finviz_data.get("fundamentals", {})),
            ("analyst_consensus", prompts.analyst_prompt, finviz_data.get("analyst", {})),
            ("insider_activity", prompts.insider_prompt, insider_data),
            ("technicals", prompts.technicals_prompt, finviz_data.get("technicals", {})),
            ("sentiment", prompts.sentiment_prompt, {**news_data, "provider_news": provider_news}),
        ]

        for category, prompt_fn, data in categories:
            input_hash = hashlib.sha256(
                json.dumps(data, sort_keys=True, default=str).encode()
            ).hexdigest()
            cached = await self.db.get_cached_analysis(symbol, category, input_hash)
            if cached:
                yield RefreshProgress(symbol=symbol, step=f"Using cached {category}...", category=category)
                score = cached["score"]
                confidence = cached["confidence"]
                cat_narrative = cached.get("narrative", "Analysis unavailable.")
            else:
                yield RefreshProgress(symbol=symbol, step=f"Analyzing {category}...", category=category)
                prompt = prompt_fn(symbol, data)
                result = _validate_signal_result(await self.llm.analyze(prompt))
                score = result["score"]
                confidence = result["confidence"]
                cat_narrative = result.get("narrative", "Analysis unavailable.")

                # For technicals, append support/resistance/entry info to narrative
                if category == "technicals":
                    extras = []
                    if result.get("support_levels"):
                        extras.append("**Support Levels:** " + " | ".join(result["support_levels"]))
                    if result.get("resistance_levels"):
                        extras.append("**Resistance Levels:** " + " | ".join(result["resistance_levels"]))
                    if result.get("entry_price"):
                        extras.append("**Suggested Entry:** " + result["entry_price"])
                    if result.get("stop_loss"):
                        extras.append("**Stop-Loss:** " + result["stop_loss"])
                    if extras:
                        cat_narrative += "\n\n" + "\n\n".join(extras)

                await self.db.save_analysis(
                    symbol=symbol, category=category, score=score,
                    confidence=confidence, narrative=cat_narrative,
                    raw_data=json.dumps(data, default=str),
                    input_hash=input_hash,
                )

            signal_results[category] = {"score": score, "confidence": confidence, "narrative": cat_narrative}

        # Sector context (needs sector param)
        sector_hash = hashlib.sha256(
            json.dumps(sector_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        cached_sector = await self.db.get_cached_analysis(symbol, "sector_context", sector_hash)
        if cached_sector:
            yield RefreshProgress(symbol=symbol, step="Using cached sector context...", category="sector_context")
            signal_results["sector_context"] = {
                "score": cached_sector["score"],
                "confidence": cached_sector["confidence"],
                "narrative": cached_sector.get("narrative", ""),
            }
        else:
            yield RefreshProgress(symbol=symbol, step="Analyzing sector context...", category="sector_context")
            sector_prompt = prompts.sector_prompt(symbol, sector or "Unknown", sector_data)
            result = _validate_signal_result(await self.llm.analyze(sector_prompt))
            signal_results["sector_context"] = {
                "score": result["score"],
                "confidence": result["confidence"],
                "narrative": result.get("narrative", ""),
            }
            await self.db.save_analysis(
                symbol=symbol, category="sector_context",
                score=result["score"], confidence=result["confidence"],
                narrative=result.get("narrative", ""), raw_data=json.dumps(sector_data, default=str),
                input_hash=sector_hash,
            )

        # Risk assessment
        risk_hash = hashlib.sha256(
            json.dumps(all_scraped, sort_keys=True, default=str).encode()
        ).hexdigest()
        cached_risk = await self.db.get_cached_analysis(symbol, "risk_assessment", risk_hash)
        if cached_risk:
            yield RefreshProgress(symbol=symbol, step="Using cached risk assessment...", category="risk_assessment")
            signal_results["risk_assessment"] = {
                "score": cached_risk["score"],
                "confidence": cached_risk["confidence"],
                "narrative": cached_risk.get("narrative", ""),
                "bull_case": "",
                "bear_case": "",
            }
        else:
            yield RefreshProgress(symbol=symbol, step="Analyzing risk...", category="risk_assessment")
            risk_prompt_text = prompts.risk_prompt(symbol, all_scraped)
            result = _validate_signal_result(await self.llm.analyze(risk_prompt_text))
            signal_results["risk_assessment"] = {
                "score": result["score"],
                "confidence": result["confidence"],
                "narrative": result.get("narrative", ""),
                "bull_case": result.get("bull_case", ""),
                "bear_case": result.get("bear_case", ""),
            }
            await self.db.save_analysis(
                symbol=symbol, category="risk_assessment",
                score=result["score"], confidence=result["confidence"],
                narrative=result.get("narrative", ""), raw_data=json.dumps(all_scraped, default=str),
                input_hash=risk_hash,
            )

        # 6. Synthesis
        yield RefreshProgress(symbol=symbol, step="Generating overall recommendation...", category=None)
        synthesis_prompt = prompts.synthesis_prompt(symbol, signal_results)
        synthesis = await self.llm.analyze(synthesis_prompt)
        raw_overall = synthesis.get("overall_score", weighted_score(
            {k: v["score"] for k, v in signal_results.items()}
        ))
        overall_score = max(-10, min(10, raw_overall))
        if overall_score != raw_overall:
            logger.warning(
                "Overall score %s out of range [-10, +10], clamped to %s",
                raw_overall, overall_score,
            )
        recommendation = synthesis.get("recommendation", score_to_recommendation(overall_score))
        # Combine narrative with entry strategy
        narrative = synthesis.get("narrative", "")
        entry_strategy = synthesis.get("entry_strategy", "")
        if entry_strategy:
            narrative += "\n\n## Entry Strategy\n\n" + entry_strategy

        await self.db.save_synthesis(
            symbol=symbol,
            overall_score=overall_score,
            recommendation=recommendation,
            narrative=narrative,
            signal_scores=json.dumps({k: v["score"] for k, v in signal_results.items()}),
        )

        yield RefreshProgress(symbol=symbol, step="Complete", done=True)

    async def close(self):
        await self.data_provider.close()
        await self.openinsider.close()
        await self.investegate.close()
        await self.news.close()
        await self.sector.close()
