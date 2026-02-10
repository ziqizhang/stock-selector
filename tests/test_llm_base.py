import pytest
from src.analysis.llm_base import LLMProvider


class DummyProvider(LLMProvider):
    """Concrete subclass for testing the base class."""

    async def analyze(self, prompt: str) -> dict:
        return self._parse_response(prompt)


def test_parse_response_valid_json():
    provider = DummyProvider()
    result = provider._parse_response('{"score": 5, "confidence": "high"}')
    assert result == {"score": 5, "confidence": "high"}


def test_parse_response_json_code_block():
    text = 'Some text\n```json\n{"score": 3}\n```\nMore text'
    provider = DummyProvider()
    result = provider._parse_response(text)
    assert result == {"score": 3}


def test_parse_response_generic_code_block():
    text = 'Result:\n```\n{"score": 7, "narrative": "ok"}\n```'
    provider = DummyProvider()
    result = provider._parse_response(text)
    assert result == {"score": 7, "narrative": "ok"}


def test_parse_response_narrative_fallback():
    text = "This is a plain text response with no JSON."
    provider = DummyProvider()
    result = provider._parse_response(text)
    assert result == {"narrative": text, "parse_error": True}


def test_parse_response_invalid_json_in_code_block():
    text = "```json\nnot valid json\n```"
    provider = DummyProvider()
    result = provider._parse_response(text)
    assert result["parse_error"] is True


def test_parse_response_empty_string():
    provider = DummyProvider()
    result = provider._parse_response("")
    assert result == {"narrative": "", "parse_error": True}


def test_llm_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider()


@pytest.mark.asyncio
async def test_dummy_provider_analyze():
    provider = DummyProvider()
    result = await provider.analyze('{"score": 1}')
    assert result == {"score": 1}
