import json
import logging
import os
from typing import AsyncGenerator
from src.scrapers.finviz import FinvizScraper
from src.scrapers.openinsider import OpenInsiderScraper
from src.scrapers.news import NewsScraper
from src.scrapers.sector import SectorScraper
from src.analysis.claude import ClaudeCLI
from src.analysis.codex import CodexCLI
from src.analysis import prompts
from src.analysis.scoring import weighted_score, score_to_recommendation
from src.db import Database
from src.models import RefreshProgress

logger = logging.getLogger(__name__)


class AnalysisEngine:
    def __init__(self, db: Database):
        self.db = db
        backend = os.environ.get("STOCK_SELECTOR_LLM", "codex").lower()
        if backend == "claude":
            self.llm = ClaudeCLI()
        elif backend == "codex":
            self.llm = CodexCLI()
        else:
            raise ValueError("STOCK_SELECTOR_LLM must be 'codex' or 'claude'")
        cache_get = db.get_cached_scrape
        cache_save = db.save_scrape_cache
        self.finviz = FinvizScraper(cache_get=cache_get, cache_save=cache_save)
        self.openinsider = OpenInsiderScraper(cache_get=cache_get, cache_save=cache_save)
        self.news = NewsScraper(cache_get=cache_get, cache_save=cache_save)
        self.sector = SectorScraper(cache_get=cache_get, cache_save=cache_save)

    async def analyze_ticker(self, symbol: str) -> AsyncGenerator[RefreshProgress, None]:
        """Run full analysis for a ticker, yielding progress updates."""
        ticker = await self.db.get_ticker(symbol)
        if not ticker:
            yield RefreshProgress(symbol=symbol, step="error", done=True)
            return

        sector = ticker.get("sector")
        all_scraped = {}
        signal_results = {}

        # 1. Scrape from Finviz (fundamentals + technicals + analyst + news)
        yield RefreshProgress(symbol=symbol, step="Scraping Finviz...", category="fundamentals")
        try:
            finviz_data = await self.finviz.scrape(symbol)
            all_scraped["finviz"] = finviz_data
        except Exception as e:
            logger.error(f"Finviz scrape failed for {symbol}: {e}")
            finviz_data = {"fundamentals": {}, "analyst": {}, "technicals": {}, "news": []}
            all_scraped["finviz"] = finviz_data

        # 2. Scrape insider activity
        yield RefreshProgress(symbol=symbol, step="Scraping OpenInsider...", category="insider_activity")
        try:
            insider_data = await self.openinsider.scrape(symbol)
            all_scraped["openinsider"] = insider_data
        except Exception as e:
            logger.error(f"OpenInsider scrape failed for {symbol}: {e}")
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
            sector_data = await self.sector.scrape(symbol, sector)
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
            ("sentiment", prompts.sentiment_prompt, {**news_data, "finviz_news": finviz_data.get("news", [])}),
        ]

        for category, prompt_fn, data in categories:
            yield RefreshProgress(symbol=symbol, step=f"Analyzing {category}...", category=category)
            prompt = prompt_fn(symbol, data)
            result = await self.llm.analyze(prompt)
            score = result.get("score", 0)
            confidence = result.get("confidence", "low")
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

            signal_results[category] = {"score": score, "confidence": confidence, "narrative": cat_narrative}
            await self.db.save_analysis(
                symbol=symbol, category=category, score=score,
                confidence=confidence, narrative=cat_narrative,
                raw_data=json.dumps(data, default=str),
            )

        # Sector context (needs sector param)
        yield RefreshProgress(symbol=symbol, step="Analyzing sector context...", category="sector_context")
        sector_prompt = prompts.sector_prompt(symbol, sector or "Unknown", sector_data)
        result = await self.llm.analyze(sector_prompt)
        signal_results["sector_context"] = {
            "score": result.get("score", 0),
            "confidence": result.get("confidence", "low"),
            "narrative": result.get("narrative", ""),
        }
        await self.db.save_analysis(
            symbol=symbol, category="sector_context",
            score=result.get("score", 0), confidence=result.get("confidence", "low"),
            narrative=result.get("narrative", ""), raw_data=json.dumps(sector_data, default=str),
        )

        # Risk assessment
        yield RefreshProgress(symbol=symbol, step="Analyzing risk...", category="risk_assessment")
        risk_prompt_text = prompts.risk_prompt(symbol, all_scraped)
        result = await self.llm.analyze(risk_prompt_text)
        signal_results["risk_assessment"] = {
            "score": result.get("score", 0),
            "confidence": result.get("confidence", "low"),
            "narrative": result.get("narrative", ""),
            "bull_case": result.get("bull_case", ""),
            "bear_case": result.get("bear_case", ""),
        }
        await self.db.save_analysis(
            symbol=symbol, category="risk_assessment",
            score=result.get("score", 0), confidence=result.get("confidence", "low"),
            narrative=result.get("narrative", ""), raw_data=json.dumps(all_scraped, default=str),
        )

        # 6. Synthesis
        yield RefreshProgress(symbol=symbol, step="Generating overall recommendation...", category=None)
        synthesis_prompt = prompts.synthesis_prompt(symbol, signal_results)
        synthesis = await self.llm.analyze(synthesis_prompt)
        overall_score = synthesis.get("overall_score", weighted_score(
            {k: v["score"] for k, v in signal_results.items()}
        ))
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
        await self.finviz.close()
        await self.openinsider.close()
        await self.news.close()
        await self.sector.close()
