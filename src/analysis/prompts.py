SYSTEM_INSTRUCTION = """You are a stock analyst assistant. Analyze the provided data and respond with ONLY valid JSON matching the specified schema. No markdown, no explanation outside the JSON.

FORMATTING RULES for all narrative fields:
- Use markdown headers (### for sections), **bold** for key numbers and metrics, *italic* for emphasis
- Put important numbers in bold: **$323.10**, **P/E 29.9**, **RSI 44.6**
- Use bullet points for lists of key metrics or factors
- Use tables (markdown) when comparing multiple data points side by side
- Keep paragraphs short (2-3 sentences max) for readability
- Start each section with the most important takeaway"""


def fundamentals_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the fundamental data for {symbol}:

{_format_data(data)}

Structure your narrative with these sections:
### Key Metrics — table of the most important numbers (P/E, EPS, margins, growth)
### Valuation — is it cheap/fair/expensive vs sector and historical averages?
### Growth — revenue and earnings trajectory
### Financial Health — debt, cash position, profitability

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10, where -10 is extremely bearish and 10 is extremely bullish>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown analysis following the sections above>"
}}"""


def analyst_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the analyst consensus data for {symbol}:

{_format_data(data)}

Consider: price targets vs current price, buy/hold/sell distribution, recent upgrades/downgrades.

Structure your narrative with:
### Price Target — current price vs analyst target, upside/downside percentage in bold
### Consensus Rating — the recommendation score and what it means
### Institutional View — ownership levels, recent changes

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown analysis following the sections above>"
}}"""


def insider_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze insider and institutional trading activity for {symbol}:

{_format_data(data)}

Consider: cluster buys (multiple insiders buying), trade sizes, insider roles (CEO/CFO buys are stronger signals), timing relative to earnings.

Structure your narrative with:
### Summary — one-line verdict (e.g. "Net insider selling, but mechanical in nature")
### Notable Trades — table of the most significant recent trades with date, insider, type, and value in bold
### Signal Interpretation — what the pattern means for investors

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown analysis following the sections above>"
}}"""


def technicals_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the technical indicators for {symbol}:

{_format_data(data)}

Consider: RSI (oversold < 30, overbought > 70), support/resistance levels from SMA20/SMA50/SMA200 and 52W High/Low, moving average crossovers, volume trends, Bollinger Band position.

IMPORTANT: Calculate and provide specific price levels.

Structure your narrative with:
### Current Position — price relative to key moving averages, trend direction
### Key Levels — use a markdown table:
| Level | Price | Type | Notes |
### Momentum — RSI, volume analysis, trend strength
### Trade Setup — the suggested entry zone, stop-loss, and risk/reward

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown analysis following the sections above>",
    "support_levels": ["<$price - description>", "<$price - description>"],
    "resistance_levels": ["<$price - description>", "<$price - description>"],
    "entry_price": "<suggested entry price or range, e.g. $310-$315>",
    "stop_loss": "<suggested stop-loss price, e.g. $295>"
}}"""


def sentiment_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze news sentiment and social media discussion for {symbol}:

{_format_data(data)}

Consider: news tone (positive/negative), event significance, social media buzz, earnings call sentiment if available.

Structure your narrative with:
### Sentiment Overview — one-line verdict (bullish/bearish/mixed) with confidence
### Key Headlines — bullet list of the most impactful recent news items, bold the headline
### Market Impact — how news is likely to affect the stock near-term

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown analysis following the sections above>"
}}"""


def sector_prompt(symbol: str, sector: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the sector context for {symbol} in the {sector} sector:

{_format_data(data)}

Consider: is the stock moving with or against the sector? Is this a sector-wide trend or stock-specific? Sector rotation implications.

Structure your narrative with:
### Sector Performance — table of sector returns (week, month, YTD) if available
### Relative Strength — is {symbol} outperforming or underperforming its sector?
### Sector Trends — rotation patterns, macro drivers affecting the sector

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown analysis following the sections above>"
}}"""


def risk_prompt(symbol: str, all_data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Provide a risk assessment for {symbol} based on all available data:

{_format_data(all_data)}

Structure your narrative with:
### Risk Summary — overall risk level (Low/Medium/High) in bold, one sentence why
### Key Risks — bullet list, each risk bolded with brief explanation
### Upcoming Catalysts — events that could move the stock (earnings dates, etc.)

Structure bull_case and bear_case each with:
- **Target Price:** bold the price
- **Key Drivers:** bullet list
- **Probability:** your estimate

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10, where negative means high risk>,
    "confidence": "<low|medium|high>",
    "narrative": "<structured markdown risk assessment following the sections above>",
    "bull_case": "<structured markdown bull case>",
    "bear_case": "<structured markdown bear case>"
}}"""


def synthesis_prompt(symbol: str, signal_results: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

You have analyzed {symbol} across multiple signal categories. Here are the results:

{_format_data(signal_results)}

Synthesize all signals into an overall recommendation. Weight the signals appropriately — fundamentals and technicals typically carry more weight for medium-term holds, while sentiment and news matter more for short-term.

Structure your narrative with:
### Recommendation — **BUY**, **HOLD**, or **SELL** in bold, followed by one-sentence rationale
### Signal Summary — markdown table of all signals with score and one-line takeaway:
| Signal | Score | Takeaway |
### Key Drivers — the 2-3 most important factors driving the recommendation
### What to Watch — upcoming events or levels that could change the thesis

Structure entry_strategy with:
### Entry Zone — bold the price range (e.g. **$310–$315**)
### Stop-Loss — bold the price (e.g. **$295**)
### Position Sizing — suggestion based on conviction level
### Risk/Reward — expected upside vs downside in bold

Respond with this exact JSON structure:
{{
    "overall_score": <float from -10 to 10>,
    "recommendation": "<buy|hold|sell>",
    "narrative": "<structured markdown synthesis following the sections above>",
    "signal_scores": {{<category>: <score> for each signal}},
    "entry_strategy": "<structured markdown entry strategy following the sections above>"
}}"""


def _format_data(data: dict) -> str:
    """Format a dict as readable text for the prompt."""
    import json
    return json.dumps(data, indent=2, default=str)
