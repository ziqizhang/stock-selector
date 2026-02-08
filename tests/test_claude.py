import pytest
import json
from unittest.mock import AsyncMock, patch
from src.analysis.claude import ClaudeCLI


@pytest.mark.asyncio
async def test_claude_cli_returns_parsed_json():
    mock_result = json.dumps({"score": 7.5, "confidence": "high", "narrative": "test"})
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = ClaudeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"score": 7.5, "confidence": "high", "narrative": "test"}
