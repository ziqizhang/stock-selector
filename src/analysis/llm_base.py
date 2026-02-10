import json
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base class for LLM CLI wrappers with shared response parsing."""

    @abstractmethod
    async def analyze(self, prompt: str) -> dict:
        """Send a prompt to the LLM and return parsed JSON."""

    def _parse_response(self, text: str) -> dict:
        """Extract JSON from LLM output, handling markdown code blocks."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        return {"narrative": text, "parse_error": True}
