SYSTEM_INSTRUCTION = """You are a stock analyst assistant. Analyze the provided data and respond with ONLY valid JSON matching the specified schema. No markdown, no explanation outside the JSON."""


def fundamentals_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the fundamental data for {symbol}:

{_format_data(data)}

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10, where -10 is extremely bearish and 10 is extremely bullish>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of the fundamentals>"
}}"""


def analyst_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the analyst consensus data for {symbol}:

{_format_data(data)}

Consider: price targets vs current price, buy/hold/sell distribution, recent upgrades/downgrades.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of analyst consensus>"
}}"""


def insider_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze insider and institutional trading activity for {symbol}:

{_format_data(data)}

Consider: cluster buys (multiple insiders buying), trade sizes, insider roles (CEO/CFO buys are stronger signals), timing relative to earnings.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of insider activity>"
}}"""


def technicals_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the technical indicators for {symbol}:

{_format_data(data)}

Consider: RSI (oversold < 30, overbought > 70), support/resistance levels, moving average crossovers, volume trends, MACD signal, Bollinger Band position.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of technicals>"
}}"""


def sentiment_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze news sentiment and social media discussion for {symbol}:

{_format_data(data)}

Consider: news tone (positive/negative), event significance, social media buzz, earnings call sentiment if available.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of sentiment>"
}}"""


def sector_prompt(symbol: str, sector: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the sector context for {symbol} in the {sector} sector:

{_format_data(data)}

Consider: is the stock moving with or against the sector? Is this a sector-wide trend or stock-specific? Sector rotation implications.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of sector context>"
}}"""


def risk_prompt(symbol: str, all_data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Provide a risk assessment for {symbol} based on all available data:

{_format_data(all_data)}

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10, where negative means high risk>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown risk assessment>",
    "bull_case": "<1-2 paragraph bull case>",
    "bear_case": "<1-2 paragraph bear case>"
}}"""


def synthesis_prompt(symbol: str, signal_results: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

You have analyzed {symbol} across multiple signal categories. Here are the results:

{_format_data(signal_results)}

Synthesize all signals into an overall recommendation. Weight the signals appropriately — fundamentals and technicals typically carry more weight for medium-term holds, while sentiment and news matter more for short-term.

Respond with this exact JSON structure:
{{
    "overall_score": <float from -10 to 10>,
    "recommendation": "<buy|hold|sell>",
    "narrative": "<3-5 paragraph markdown synthesis explaining the overall picture, key drivers, and what to watch>",
    "signal_scores": {{<category>: <score> for each signal}}
}}"""


def _format_data(data: dict) -> str:
    """Format a dict as readable text for the prompt."""
    import json
    return json.dumps(data, indent=2, default=str)
