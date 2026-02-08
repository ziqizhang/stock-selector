import pytest
import json
from unittest.mock import AsyncMock, patch
from src.analysis.claude import ClaudeCLI
from src.analysis.codex import CodexCLI


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


@pytest.mark.asyncio
async def test_codex_cli_returns_parsed_json():
    mock_result = json.dumps({"score": 7.5, "confidence": "high", "narrative": "test"})
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = CodexCLI(cmd_template="codex exec")
        result = await cli.analyze("test prompt")
        assert result == {"score": 7.5, "confidence": "high", "narrative": "test"}


@pytest.mark.asyncio
async def test_codex_cli_parses_json_stream_output():
    agent_payload = json.dumps({"score": 5.0, "confidence": "medium", "narrative": "ok"})
    stream = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "t1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps({
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": agent_payload},
        }),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}),
    ])
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (stream.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = CodexCLI(cmd_template="codex exec --json {prompt}")
        result = await cli.analyze("test prompt")
        assert result == {"score": 5.0, "confidence": "medium", "narrative": "ok"}


@pytest.mark.asyncio
async def test_codex_cli_fails_fast_on_invalid_json_stream():
    stream = "\n".join([
        json.dumps({"type": "thread.started", "thread_id": "t1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps({
            "type": "item.completed",
            "item": {"id": "item_0", "type": "agent_message", "text": "not json"},
        }),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}),
    ])
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (stream.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = CodexCLI(cmd_template="codex exec --json {prompt}")
        result = await cli.analyze("test prompt")
        assert result["parse_error"] is True
        assert "error" in result
