import pytest
import json
from unittest.mock import AsyncMock, patch
from src.analysis.opencode import OpencodeCLI


@pytest.mark.asyncio
async def test_opencode_cli_returns_parsed_json():
    mock_result = json.dumps({"score": 7.5, "confidence": "high", "narrative": "test"})
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = OpencodeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"score": 7.5, "confidence": "high", "narrative": "test"}


@pytest.mark.asyncio
async def test_opencode_cli_handles_markdown_json():
    mock_result = "```json\n{\"score\": 6.0, \"confidence\": \"medium\", \"narrative\": \"analysis\"}\n```"
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = OpencodeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"score": 6.0, "confidence": "medium", "narrative": "analysis"}


@pytest.mark.asyncio
async def test_opencode_cli_handles_narrative_response():
    mock_result = "This is a narrative response without JSON"
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = OpencodeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"narrative": "This is a narrative response without JSON", "parse_error": True}


@pytest.mark.asyncio
async def test_opencode_cli_handles_command_error():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Command not found")
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        cli = OpencodeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"error": "Command not found"}


@pytest.mark.asyncio
async def test_opencode_cli_handles_file_not_found():
    with patch("shutil.which", return_value=None):
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            cli = OpencodeCLI()
            result = await cli.analyze("test prompt")
            assert result == {"error": "Opencode CLI not found"}


@pytest.mark.asyncio
async def test_opencode_cli_parses_json_stream_output():
    text_payload = json.dumps({"score": 5.0, "confidence": "medium", "narrative": "analysis complete"})
    stream = "\n".join([
        json.dumps({
            "type": "step_start", 
            "timestamp": 1770663016916, 
            "sessionID": "ses_3bc4291c3ffe5PQbWY1SD6HbxW",
            "part": {"id": "prt_c43bd79d2001Pkw9xCSnOw3tLH", "type": "step-start"}
        }),
        json.dumps({
            "type": "text",
            "timestamp": 1770663017400,
            "sessionID": "ses_3bc4291c3ffe5PQbWY1SD6HbxW",
            "part": {
                "id": "prt_c43bd7a68001FiDgLIqa48GvUa",
                "type": "text",
                "text": text_payload
            }
        }),
        json.dumps({
            "type": "step_finish",
            "timestamp": 1770663017401,
            "sessionID": "ses_3bc4291c3ffe5PQbWY1SD6HbxW",
            "part": {"id": "prt_c43bd7bb8001qeSHAdB9qtOFi2", "type": "step-finish", "reason": "stop"}
        })
    ])
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (stream.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = OpencodeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"score": 5.0, "confidence": "medium", "narrative": "analysis complete"}


@pytest.mark.asyncio
async def test_opencode_cli_custom_cmd_template():
    mock_result = json.dumps({"score": 8.0, "confidence": "high", "narrative": "custom"})
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = OpencodeCLI(cmd_template="opencode run {prompt} --format json --model gpt-4")
        result = await cli.analyze("test prompt")
        assert result == {"score": 8.0, "confidence": "high", "narrative": "custom"}